from typing import Optional, Dict, Any
from datetime import datetime
from pydantic import BaseModel, Field

class IngestionMetrics(BaseModel):
    logs_received: int = 0
    logs_processed: int = 0
    logs_failed: int = 0
    logs_buffered: int = 0
    buffer_utilization: float = 0.0  # 0.0 - 1.0
    avg_processing_time_ms: Optional[float] = None
    max_processing_time_ms: Optional[float] = None
    min_processing_time_ms: Optional[float] = None
    error_rate: Optional[float] = None
    throughput_logs_per_sec: Optional[float] = None
    last_ingestion_time: Optional[datetime] = None
    last_export_time: Optional[datetime] = None

class ExporterMetrics(BaseModel):
    logs_exported: int = 0
    export_failures: int = 0
    last_export_time: Optional[datetime] = None
    downstream_latency_ms: Optional[float] = None
    exporter_name: Optional[str] = None

class SystemResourceMetrics(BaseModel):
    cpu_percent: Optional[float] = None
    memory_percent: Optional[float] = None
    disk_percent: Optional[float] = None
    open_file_descriptors: Optional[int] = None
    process_count: Optional[int] = None
    timestamp: Optional[datetime] = None

class MetricsSnapshot(BaseModel):
    ingestion_metrics: IngestionMetrics
    exporter_metrics: Optional[Dict[str, ExporterMetrics]] = Field(default_factory=dict)
    system_metrics: Optional[SystemResourceMetrics] = None
    custom_metrics: Optional[Dict[str, Any]] = Field(default_factory=dict)
    snapshot_time: datetime

# Optionally extend ProcessingStats here if you want richer aggregation
# (already defined in log_models.py for per-log/batch stats) 