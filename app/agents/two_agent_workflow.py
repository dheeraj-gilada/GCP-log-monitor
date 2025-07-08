import os
import asyncio
from agents import Agent, Runner, function_tool, set_default_openai_client
from app.agents.redis_tools import AnomalyGroupingTools
from app.services.log_storage_manager import LogStorageManager
from app.models.rca_schema import AlertReport, SeverityLevel, GroupIndexRange
from typing import List, Dict, Any
from pydantic import BaseModel
import instructor
from openai import AsyncOpenAI

# --- Agent 1: Grouping Agent ---
class GroupingAgent:
    def __init__(self, anomaly_logs: List[Dict[str, Any]]):
        self.anomaly_logs = anomaly_logs

    def as_agent(self):
        @function_tool
        async def get_anomaly_logs() -> List[Dict[str, Any]]:
            # Just return the anomaly logs provided
            return self.anomaly_logs
        return Agent(
            name="anomaly-grouping-agent",
            instructions=(
                "You are an LLM agent for grouping anomaly logs.\n"
                "Input: A list of anomaly logs (each with log_index, timestamp, message, etc).\n"
                "Task: Group these anomalies by similarity, temporal proximity, or other logical criteria.\n"
                "Output: For each group, return a GroupIndexRange (start, end, group_id, description).\n"
                "Return a list of such groups. Do not analyze the logs, just group them."
            ),
            model="gpt-4o",
            tools=[get_anomaly_logs],
            output_type=List[GroupIndexRange],
        )

# --- Agent 2: Analysis Agent ---
class AnalysisAgent:
    def __init__(self, log_storage: LogStorageManager, api_key: str = None):
        self.log_storage = log_storage
        self.api_key = api_key or os.environ.get("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY not set in environment or .env file.")
        self.client = instructor.from_openai(AsyncOpenAI(api_key=self.api_key))
        set_default_openai_client(self.client)

    def as_agent(self):
        def make_get_logs_by_index_tool(log_storage):
            @function_tool
            async def get_logs_by_index(start: int, end: int) -> List[Dict[str, Any]]:
                return await log_storage.get_logs_range(start, end)
            return get_logs_by_index
        return Agent(
            name="incident-analysis-agent",
            instructions=(
                "You are an LLM agent for analyzing a group of logs.\n"
                "Input: A group index range (start, end).\n"
                "You have a tool to fetch all normalized logs in this range from Redis.\n"
                "Task: Fetch the logs, analyze the incident, and return a structured alert report (AlertReport).\n"
                "Output: One AlertReport for this group."
            ),
            model="gpt-4o",
            tools=[make_get_logs_by_index_tool(self.log_storage)],
            output_type=AlertReport,
        )

# --- Orchestration ---
async def run_two_agent_workflow_stream(log_storage: LogStorageManager, lookback: int = 1000, api_key: str = None):
    # 1. Get all anomalies in the lookback window
    max_index = await log_storage.get_current_max_index()
    start_index = max(0, max_index - lookback)
    anomaly_indices = await log_storage.get_anomaly_indices(start_index, max_index)
    if not anomaly_indices:
        print("[DEBUG] No anomalies found in the lookback window. Skipping LLM calls.")
        return
    print(f"[DEBUG] Found {len(anomaly_indices)} anomalies in range {start_index}-{max_index}.")
    anomaly_logs = await log_storage.get_logs_range(min(anomaly_indices), max(anomaly_indices))
    anomaly_logs = [log for log in anomaly_logs if log.get("is_anomaly")]  # Defensive
    print(f"[DEBUG] Sending {len(anomaly_logs)} anomaly logs to Agent 1 (Grouping Agent)")

    # 2. Call Agent 1 to group anomalies
    grouping_agent = GroupingAgent(anomaly_logs).as_agent()
    grouping_prompt = (
        "Group these anomaly logs into related groups. For each group, return a GroupIndexRange (start, end, group_id, description)."
    )
    print(f"[DEBUG] Grouping prompt: {grouping_prompt}")
    groupings = await Runner.run(grouping_agent, input=grouping_prompt)
    group_ranges = groupings.final_output if hasattr(groupings, 'final_output') else groupings
    print(f"[DEBUG] Agent 1 returned {len(group_ranges) if group_ranges else 0} groups. Example: {group_ranges[0] if group_ranges else 'None'}")

    # 3. For each group, call Agent 2 for analysis
    analysis_agent = AnalysisAgent(log_storage, api_key=api_key).as_agent()
    for i, group in enumerate(group_ranges or []):
        analysis_prompt = (
            f"Analyze the logs in group {i} (log_index {group.start} to {group.end}). "
            "Use the tool to fetch all normalized logs in this range. "
            "Return a structured alert report (AlertReport) for this group."
        )
        print(f"[DEBUG] Sending to Agent 2 (Analysis Agent), group {i}: {group}")
        result = await Runner.run(analysis_agent, input=analysis_prompt, context={"start": group.start, "end": group.end})
        alert_report = result.final_output
        yield alert_report.model_dump(mode='json')

async def run_two_agent_workflow_batch(log_storage: LogStorageManager, lookback: int = 1000, api_key: str = None):
    # 1. Get all anomalies in the lookback window
    max_index = await log_storage.get_current_max_index()
    start_index = max(0, max_index - lookback)
    anomaly_indices = await log_storage.get_anomaly_indices(start_index, max_index)
    if not anomaly_indices:
        print("[DEBUG] No anomalies found in the lookback window. Skipping LLM calls.")
        return []
    print(f"[DEBUG] Found {len(anomaly_indices)} anomalies in range {start_index}-{max_index}.")
    anomaly_logs = await log_storage.get_logs_range(min(anomaly_indices), max(anomaly_indices))
    anomaly_logs = [log for log in anomaly_logs if log.get("is_anomaly")]  # Defensive
    print(f"[DEBUG] Sending {len(anomaly_logs)} anomaly logs to Agent 1 (Grouping Agent)")

    # 2. Call Agent 1 to group anomalies
    grouping_agent = GroupingAgent(anomaly_logs).as_agent()
    grouping_prompt = (
        "Group these anomaly logs into related groups. For each group, return a GroupIndexRange (start, end, group_id, description)."
    )
    print(f"[DEBUG] Grouping prompt: {grouping_prompt}")
    groupings = await Runner.run(grouping_agent, input=grouping_prompt)
    group_ranges = groupings.final_output if hasattr(groupings, 'final_output') else groupings
    print(f"[DEBUG] Agent 1 returned {len(group_ranges) if group_ranges else 0} groups. Example: {group_ranges[0] if group_ranges else 'None'}")

    # 3. For each group, call Agent 2 for analysis
    analysis_agent = AnalysisAgent(log_storage, api_key=api_key).as_agent()
    alert_reports = []
    for i, group in enumerate(group_ranges or []):
        analysis_prompt = (
            f"Analyze the logs in group {i} (log_index {group.start} to {group.end}). "
            "Use the tool to fetch all normalized logs in this range. "
            "Return a structured alert report (AlertReport) for this group."
        )
        print(f"[DEBUG] Sending to Agent 2 (Analysis Agent), group {i}: {group}")
        result = await Runner.run(analysis_agent, input=analysis_prompt, context={"start": group.start, "end": group.end})
        alert_report = result.final_output
        alert_reports.append(alert_report.model_dump(mode='json'))
    return alert_reports 