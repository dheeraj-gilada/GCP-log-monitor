from typing import Any, Dict, List, Optional, Union
from datetime import datetime
from pydantic import BaseModel, Field, root_validator

# --- Payload Variants ---
class JsonPayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)

class TextPayload(BaseModel):
    text: str

class ProtoPayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)

class StructPayload(BaseModel):
    data: Dict[str, Any] = Field(default_factory=dict)

PayloadType = Union[JsonPayload, TextPayload, ProtoPayload, StructPayload, Dict[str, Any], str]

# --- Correlation Context ---
class CorrelationContext(BaseModel):
    trace_id: Optional[str] = None
    span_id: Optional[str] = None
    parent_span_id: Optional[str] = None
    baggage: Dict[str, str] = Field(default_factory=dict)
    otel_context: Optional[Dict[str, Any]] = None

# --- Ingestion Metadata ---
class FileInfo(BaseModel):
    filename: str
    size_bytes: int
    uploaded_at: Optional[datetime] = None

class ProcessingStats(BaseModel):
    parse_time_ms: Optional[float] = None
    normalization_time_ms: Optional[float] = None
    total_time_ms: Optional[float] = None
    error_count: Optional[int] = 0
    warning_count: Optional[int] = 0

class IngestionMetadata(BaseModel):
    source: str  # "gcp_api", "file_upload", "stream"
    ingestion_timestamp: datetime
    original_format: str  # "gcp_json", "k8s_container", etc.
    file_info: Optional[FileInfo] = None
    processing_stats: Optional[ProcessingStats] = None

# --- Service-Specific Models (optional enrichment) ---
class GKELogEntry(BaseModel):
    pod_name: Optional[str]
    container_name: Optional[str]
    namespace_name: Optional[str]
    cluster_name: Optional[str]
    labels: Optional[Dict[str, Any]]

class CloudSQLLogEntry(BaseModel):
    database_id: Optional[str]
    region: Optional[str]
    user: Optional[str]
    labels: Optional[Dict[str, Any]]

class CloudFunctionLogEntry(BaseModel):
    function_name: Optional[str]
    region: Optional[str]
    labels: Optional[Dict[str, Any]]

class AppEngineLogEntry(BaseModel):
    module_id: Optional[str]
    version_id: Optional[str]
    instance_id: Optional[str]
    labels: Optional[Dict[str, Any]]

class LoadBalancerLogEntry(BaseModel):
    backend_service: Optional[str]
    ip: Optional[str]
    port: Optional[int]
    labels: Optional[Dict[str, Any]]

# --- Raw GCP Log Entry (schema-agnostic) ---
class RawGCPLogEntry(BaseModel):
    # Flexible fields for all GCP log types
    log_name: Optional[str] = None
    resource: Optional[Dict[str, Any]] = None
    timestamp: Optional[datetime] = None
    receive_timestamp: Optional[datetime] = None
    severity: Optional[Union[str, int]] = None
    json_payload: Optional[Dict[str, Any]] = Field(default=None, alias="jsonPayload")
    text_payload: Optional[str] = Field(default=None, alias="textPayload")
    proto_payload: Optional[Dict[str, Any]] = Field(default=None, alias="protoPayload")
    struct_payload: Optional[Dict[str, Any]] = Field(default=None, alias="structPayload")
    labels: Optional[Dict[str, Any]] = None
    insert_id: Optional[str] = None
    trace: Optional[str] = None
    span_id: Optional[str] = None
    trace_sampled: Optional[bool] = None
    source_location: Optional[Dict[str, Any]] = None
    operation: Optional[Dict[str, Any]] = None
    # Preserve the original log
    raw_log: Dict[str, Any]

    class Config:
        allow_population_by_field_name = True
        extra = "allow"
        arbitrary_types_allowed = True

# --- Normalized Log Entry ---
class NormalizedLogEntry(BaseModel):
    timestamp: datetime
    message: str
    severity: Optional[str] = None
    resource_type: Optional[str] = None
    resource_labels: Optional[Dict[str, Any]] = None
    correlation_context: Optional[CorrelationContext] = None
    ingestion_metadata: Optional[IngestionMetadata] = None
    service_specific: Optional[Union[GKELogEntry, CloudSQLLogEntry, CloudFunctionLogEntry, AppEngineLogEntry, LoadBalancerLogEntry]] = None
    raw_log: Optional[Dict[str, Any]] = None
    log_index: Optional[int] = None  # Not stored in Redis, populated on retrieval
    is_anomaly: bool = False         # Stored in Redis, updated by detector

    class Config:
        allow_population_by_field_name = True
        extra = "allow"
        arbitrary_types_allowed = True

# --- Validation & Error Handling ---
class LogValidationError(BaseModel):
    field: str
    error_type: str
    message: str
    raw_value: Any

class IngestionResult(BaseModel):
    success: bool
    processed_count: int
    failed_count: int
    validation_errors: List[LogValidationError] = Field(default_factory=list)
    processing_time_ms: float

# --- Ingestion API Contracts ---
class IngestionRequest(BaseModel):
    logs: List[Dict[str, Any]]
    source: str
    file_info: Optional[FileInfo] = None

class IngestionResponse(BaseModel):
    result: IngestionResult
    normalized_logs: Optional[List[NormalizedLogEntry]] = None

# --- Log Buffer & Processing Metrics ---
class LogBufferStatus(BaseModel):
    buffer_size: int
    max_size: int
    oldest_timestamp: Optional[datetime]
    newest_timestamp: Optional[datetime]
    dropped_count: int = 0

class ProcessingMetrics(BaseModel):
    logs_ingested: int
    logs_normalized: int
    logs_failed: int
    avg_processing_time_ms: float
    error_rate: float
    buffer_utilization: float

# --- Utility: Accept both snake_case and camelCase ---
class CamelModel(BaseModel):
    class Config:
        alias_generator = lambda s: ''.join([s[0].lower()] + [c if c.islower() else '_' + c.lower() for c in s[1:]])
        allow_population_by_field_name = True
        extra = "allow"
        arbitrary_types_allowed = True

# --- Example usage: NormalizedLogEntry inherits from CamelModel if you want camelCase support ---
# class NormalizedLogEntry(CamelModel): ... 