from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from pydantic import BaseModel, Field

class WorkflowError(BaseModel):
    error_type: str  # "parsing_error", "gcp_api_error", etc.
    stage: str       # "ingestion", "normalization", "buffering"
    recoverable: bool
    retry_count: int = 0
    context: Dict[str, Any] = Field(default_factory=dict)

class WorkflowProgress(BaseModel):
    stage: str  # "starting", "ingesting", "parsing", "buffering", "complete"
    progress_percentage: float
    estimated_completion: Optional[datetime] = None
    logs_processed: int = 0
    logs_remaining: Optional[int] = None

class WorkflowLimits(BaseModel):
    max_concurrent_runs: int = 10
    max_logs_per_run: int = 100000
    max_file_size_mb: int = 500
    timeout_seconds: int = 3600

class WorkflowHooks(BaseModel):
    on_start: Optional[Callable] = None
    on_progress: Optional[Callable] = None
    on_complete: Optional[Callable] = None
    on_error: Optional[Callable] = None
    on_anomaly_detected: Optional[Callable] = None  # Future use

class WorkflowContext(BaseModel):
    run_id: str
    source: str
    start_time: datetime
    end_time: Optional[datetime] = None
    status: str = "pending"  # "pending", "running", "completed", "failed", "cancelled"
    progress: WorkflowProgress = Field(default_factory=WorkflowProgress)
    error: Optional[WorkflowError] = None
    trace_id: Optional[str] = None
    correlation_id: Optional[str] = None
    baggage: Dict[str, Any] = Field(default_factory=dict)
    hooks: Optional[WorkflowHooks] = None
    metadata: Dict[str, Any] = Field(default_factory=dict) 