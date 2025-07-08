from pydantic import BaseModel, Field
from enum import Enum
from typing import List, Tuple, Optional

class RCAgentOutput(BaseModel):
    root_cause: str = Field(..., description="Root cause of the anomaly")
    impact: str = Field(..., description="Impact assessment of the anomaly")
    remediation: str = Field(..., description="Recommended remediation steps")

class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"

class TimelineEntry(BaseModel):
    log_index: int
    timestamp: str  # ISO8601 string is safest for OpenAI schema
    service_or_component: str
    message: str
    is_anomaly: bool

class LogIndexRange(BaseModel):
    start: int
    end: int

class GroupIndexRange(BaseModel):
    start: int
    end: int
    group_id: Optional[str] = None
    description: Optional[str] = None

class AlertReport(BaseModel):
    title: str
    severity: SeverityLevel
    affected_services: List[str]
    issue_summary: str
    timeline: List[TimelineEntry]  # Changed from List[Tuple[...]]
    root_cause_analysis: str
    impact_assessment: str
    suggested_actions: List[str]
    anomaly_count: int
    log_index_range: LogIndexRange
    confidence_score: float 