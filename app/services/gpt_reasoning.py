"""
GPT-4O reasoning service using OpenAI Agents SDK for log analysis and anomaly investigation.
Provides root cause analysis and actionable recommendations.
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from openai import AsyncOpenAI

from app.config import get_settings
from app.models.schemas import LogEntry, Anomaly, AnomalyType, LogSeverity


class LogAnalysisAgent:
    """OpenAI client wrapper for log analysis and anomaly investigation."""
    
    def __init__(self, api_key: str):
        self.client = AsyncOpenAI(api_key=api_key)
        
        # System prompt for GPT analysis
        self.system_prompt = """
        You are an expert Site Reliability Engineer (SRE) and log analysis specialist. 
        Your role is to analyze log data, identify root causes of anomalies, and provide 
        actionable recommendations for resolving issues.
        
        When analyzing logs and anomalies:
        1. Focus on identifying the root cause, not just symptoms
        2. Consider system interdependencies and cascading failures
        3. Provide specific, actionable recommendations
        4. Assess the severity and potential impact
        5. Suggest both immediate fixes and long-term improvements
        
        Always structure your analysis with:
        - Root Cause Analysis
        - Impact Assessment  
        - Immediate Actions
        - Long-term Recommendations
        - Confidence Level (0.0-1.0)
        
        Format your response as valid JSON.
        """
    
    async def run(self, prompt: str) -> str:
        """Run analysis using OpenAI GPT-4."""
        try:
            response = await self.client.chat.completions.create(
                model="gpt-4o-mini",  # Using GPT-4O Mini for cost efficiency
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logging.error(f"OpenAI API call failed: {e}")
            raise
    



class GPTReasoningService:
    """Service for AI-powered log analysis and anomaly reasoning."""
    
    def __init__(self):
        self.settings = get_settings()
        self.agent = None
        
        if self.settings.openai_api_key:
            try:
                self.agent = LogAnalysisAgent(self.settings.openai_api_key)
                logging.info("GPT Reasoning Service initialized successfully")
            except Exception as e:
                logging.error(f"Failed to initialize GPT agent: {e}")
                self.agent = None
        else:
            logging.warning("OpenAI API key not provided - GPT analysis disabled")
    
    async def analyze_anomalies(self, anomalies: List[Anomaly], logs: List[LogEntry], context: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze anomalies using GPT-4O and provide insights."""
        
        if not self.agent:
            return await self._fallback_analysis(anomalies, logs, context)
        
        try:
            # Prepare structured input for the agent
            analysis_input = {
                "anomalies": [self._serialize_anomaly(anomaly) for anomaly in anomalies],
                "log_summary": self._summarize_logs(logs),
                "context": context,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Create the analysis prompt
            prompt = self._create_analysis_prompt(analysis_input)
            
            # Get analysis from the agent
            response = await self.agent.run(prompt)
            
            # Parse and structure the response
            return await self._parse_agent_response(response, anomalies)
            
        except Exception as e:
            logging.error(f"GPT analysis failed: {e}")
            return await self._fallback_analysis(anomalies, logs, context)
    
    def _serialize_anomaly(self, anomaly: Anomaly) -> Dict[str, Any]:
        """Convert anomaly to serializable format for GPT analysis."""
        return {
            "type": anomaly.type.value,
            "severity": anomaly.severity.value,
            "confidence": anomaly.confidence,
            "description": anomaly.description,
            "affected_resources": anomaly.affected_resources,
            "time_window": {
                "start": anomaly.timestamp.isoformat(),
                "end": (anomaly.timestamp + timedelta(minutes=anomaly.time_window_minutes)).isoformat()
            },
            "metrics": anomaly.metrics,
            "detection_method": anomaly.detection_method
        }
    
    def _summarize_logs(self, logs: List[LogEntry]) -> Dict[str, Any]:
        """Create a summary of logs for GPT analysis."""
        if not logs:
            return {}
        
        severity_counts = {}
        resource_counts = {}
        error_samples = []
        
        for log in logs:
            # Count by severity
            severity = log.severity.value
            severity_counts[severity] = severity_counts.get(severity, 0) + 1
            
            # Count by resource type
            resource_type = log.resource.type.value if log.resource else "unknown"
            resource_counts[resource_type] = resource_counts.get(resource_type, 0) + 1
            
            # Collect error samples
            if log.severity in [LogSeverity.ERROR, LogSeverity.CRITICAL] and len(error_samples) < 10:
                error_samples.append({
                    "timestamp": log.timestamp.isoformat(),
                    "message": log.message[:200],  # Truncate long messages
                    "resource": resource_type
                })
        
        return {
            "total_logs": len(logs),
            "severity_distribution": severity_counts,
            "resource_distribution": resource_counts,
            "error_samples": error_samples,
            "time_span": {
                "start": min(log.timestamp for log in logs).isoformat(),
                "end": max(log.timestamp for log in logs).isoformat()
            }
        }
    
    def _create_analysis_prompt(self, analysis_input: Dict[str, Any]) -> str:
        """Create a structured prompt for GPT analysis."""
        return f"""
        Please analyze the following log anomalies and provide detailed insights:

        DETECTED ANOMALIES:
        {json.dumps(analysis_input['anomalies'], indent=2)}

        LOG SUMMARY:
        {json.dumps(analysis_input['log_summary'], indent=2)}

        CONTEXT:
        {json.dumps(analysis_input['context'], indent=2)}

        Please provide:
        1. Root cause analysis for each anomaly
        2. Severity assessment and potential impact
        3. Immediate action recommendations
        4. Long-term preventive measures
        5. Confidence level in your analysis (0.0-1.0)

        Format your response as structured JSON with the following keys:
        - root_cause_analysis
        - impact_assessment
        - immediate_actions
        - long_term_recommendations
        - confidence_score
        - enhanced_anomalies (array with additional insights for each anomaly)
        """
    
    async def _parse_agent_response(self, response: Any, anomalies: List[Anomaly]) -> Dict[str, Any]:
        """Parse and structure the agent response."""
        try:
            # Extract the response content (now it's just a string)
            content = response
            
            # Try to parse as JSON
            try:
                parsed_response = json.loads(content)
            except json.JSONDecodeError:
                # If not valid JSON, create structured response
                parsed_response = {
                    "root_cause_analysis": content,
                    "confidence_score": 0.7,
                    "enhanced_anomalies": []
                }
            
            # Ensure required fields exist
            default_response = {
                "root_cause_analysis": "AI analysis completed",
                "impact_assessment": "Moderate impact potential",
                "immediate_actions": ["Monitor system closely", "Review error logs"],
                "long_term_recommendations": ["Implement better monitoring", "Review system architecture"],
                "confidence_score": 0.7,
                "enhanced_anomalies": []
            }
            
            # Merge with defaults
            for key, default_value in default_response.items():
                if key not in parsed_response:
                    parsed_response[key] = default_value
            
            return parsed_response
            
        except Exception as e:
            logging.error(f"Error parsing agent response: {e}")
            return await self._fallback_analysis(anomalies, [], {})
    
    async def _fallback_analysis(self, anomalies: List[Anomaly], logs: List[LogEntry], context: Dict[str, Any]) -> Dict[str, Any]:
        """Provide basic analysis when GPT is unavailable."""
        
        high_severity_anomalies = [a for a in anomalies if a.severity.value in ["HIGH", "CRITICAL"]]
        
        analysis = {
            "root_cause_analysis": "Automated analysis: Multiple anomalies detected in system logs",
            "impact_assessment": f"Detected {len(anomalies)} anomalies, {len(high_severity_anomalies)} of high severity",
            "immediate_actions": [
                "Review high-severity anomalies immediately",
                "Check system resources and performance",
                "Monitor error rates closely"
            ],
            "long_term_recommendations": [
                "Implement comprehensive monitoring",
                "Set up alerting for error rate thresholds",
                "Regular log analysis and pattern detection"
            ],
            "confidence_score": 0.8,
            "enhanced_anomalies": [
                {
                    "index": i,
                    "root_cause": "Detected via statistical/pattern analysis",
                    "recommended_action": "Investigate and resolve underlying issue",
                    "confidence_adjustment": 1.0
                }
                for i in range(len(anomalies))
            ]
        }
        
        return analysis
    
    def is_available(self) -> bool:
        """Check if GPT analysis is available."""
        return self.agent is not None
    
    async def analyze_single_log_entry(self, log_entry: LogEntry) -> Dict[str, Any]:
        """Analyze a single critical log entry."""
        if not self.agent:
            return {"analysis": "GPT analysis not available", "severity": "unknown"}
        
        try:
            prompt = f"""
            Analyze this critical log entry and provide insights:
            
            Timestamp: {log_entry.timestamp}
            Severity: {log_entry.severity.value}
            Message: {log_entry.message}
            Resource: {log_entry.resource.type.value if log_entry.resource else 'unknown'}
            
            Please provide:
            1. What might have caused this log entry?
            2. Is this indicative of a larger issue?
            3. What should be investigated next?
            
            Respond with a JSON object containing 'analysis', 'potential_cause', and 'next_steps'.
            """
            
            response = await self.agent.run(prompt)
            
            try:
                return json.loads(response)
            except:
                return {"analysis": response, "potential_cause": "Unknown", "next_steps": ["Manual investigation required"]}
                
        except Exception as e:
            logging.error(f"Single log analysis failed: {e}")
            return {"analysis": f"Analysis failed: {e}", "severity": "unknown"}
