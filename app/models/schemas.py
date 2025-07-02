"""
Core Pydantic models for the GCP Log Monitoring system.
Defines data structures for logs, anomalies, alerts, and configurations.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from enum import Enum
from pydantic import BaseModel, Field, validator


class LogSeverity(str, Enum):
    """Log severity levels based on GCP Cloud Logging."""
    DEFAULT = "DEFAULT"
    DEBUG = "DEBUG"
    INFO = "INFO"
    NOTICE = "NOTICE"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"
    ALERT = "ALERT"
    EMERGENCY = "EMERGENCY"


class ResourceType(str, Enum):
    """GCP resource types for log classification."""
    CLOUDSQL_DATABASE = "cloudsql_database"
    GCE_INSTANCE = "gce_instance"
    PUBSUB_TOPIC = "pubsub_topic"
    PUBSUB_SUBSCRIPTION = "pubsub_subscription"
    K8S_CONTAINER = "k8s_container"
    CLOUD_FUNCTION = "cloud_function"
    UNKNOWN = "unknown"


class HTTPRequest(BaseModel):
    """HTTP request information from logs."""
    status: Optional[int] = None
    latency: Optional[float] = None  # in seconds
    method: Optional[str] = None
    url: Optional[str] = None
    user_agent: Optional[str] = None
    remote_ip: Optional[str] = None


class LogResource(BaseModel):
    """GCP resource information."""
    type: ResourceType
    labels: Dict[str, str] = Field(default_factory=dict)
    
    @validator('type', pre=True)
    def parse_resource_type(cls, v):
        """Parse resource type from string."""
        if isinstance(v, str):
            # Map common GCP resource types
            type_mapping = {
                "cloudsql_database": ResourceType.CLOUDSQL_DATABASE,
                "gce_instance": ResourceType.GCE_INSTANCE,
                "pubsub_topic": ResourceType.PUBSUB_TOPIC,
                "pubsub_subscription": ResourceType.PUBSUB_SUBSCRIPTION,
                "k8s_container": ResourceType.K8S_CONTAINER,
                "cloud_function": ResourceType.CLOUD_FUNCTION,
            }
            return type_mapping.get(v, ResourceType.UNKNOWN)
        return v


class LogEntry(BaseModel):
    """Normalized log entry structure."""
    timestamp: datetime
    severity: LogSeverity
    message: str
    resource: LogResource
    http_request: Optional[HTTPRequest] = None
    json_payload: Dict[str, Any] = Field(default_factory=dict)
    labels: Dict[str, str] = Field(default_factory=dict)
    trace: Optional[str] = None
    span_id: Optional[str] = None
    
    # Internal fields
    source: str = Field(default="unknown")  # "gcp" or "file"
    raw_log: Optional[str] = None
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AnomalyType(str, Enum):
    """Types of anomalies detected."""
    HIGH_ERROR_RATE = "high_error_rate"
    HIGH_LATENCY = "high_latency"
    REPEATED_ERRORS = "repeated_errors"
    UNUSUAL_PATTERN = "unusual_pattern"
    DEPLOYMENT_CORRELATION = "deployment_correlation"
    RESOURCE_EXHAUSTION = "resource_exhaustion"


class AnomalySeverity(str, Enum):
    """Severity levels for anomalies."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class DetectionMethod(str, Enum):
    """Method used to detect the anomaly."""
    STATISTICAL = "statistical"
    PATTERN = "pattern"
    CORRELATION = "correlation"
    AI_ANALYSIS = "ai_analysis"


class Anomaly(BaseModel):
    """Detected anomaly with context."""
    id: str = Field(..., description="Unique anomaly identifier")
    type: AnomalyType
    severity: AnomalySeverity
    detection_method: DetectionMethod
    
    # Core information
    title: str
    description: str
    timestamp: datetime
    
    # Metrics
    affected_logs_count: int
    metric_value: Optional[float] = None
    threshold_value: Optional[float] = None
    confidence: float = Field(default=0.8, description="Confidence score (0.0-1.0)")
    
    # Context
    resource_type: ResourceType
    resource_labels: Dict[str, str] = Field(default_factory=dict)
    affected_resources: List[str] = Field(default_factory=list, description="List of affected resource types/names")
    time_window_minutes: int = Field(default=10)
    
    # Related data
    sample_logs: List[LogEntry] = Field(default_factory=list, max_items=5)
    patterns: List[str] = Field(default_factory=list)
    correlations: List[str] = Field(default_factory=list)
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class AlertType(str, Enum):
    """Types of alerts generated."""
    ERROR_RATE = "error_rate"
    VOLUME_SPIKE = "volume_spike"
    LATENCY_SPIKE = "latency_spike"
    RESOURCE_EXHAUSTION = "resource_exhaustion"
    REPEATED_ERRORS = "repeated_errors"
    GENERAL = "general"


class AlertStatus(str, Enum):
    """Alert processing status."""
    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    SUPPRESSED = "suppressed"


class Alert(BaseModel):
    """Generated alert with AI analysis."""
    id: str = Field(..., description="Unique alert identifier")
    anomaly_id: str = Field(..., description="Related anomaly ID")
    
    # Alert classification
    alert_type: AlertType = AlertType.GENERAL
    
    # Alert content
    title: str
    summary: str
    root_cause_analysis: Optional[str] = None
    recommended_actions: List[str] = Field(default_factory=list)
    
    # Metadata
    created_at: datetime
    severity: AnomalySeverity
    status: AlertStatus = AlertStatus.PENDING
    
    # Email content
    html_content: Optional[str] = None
    markdown_content: Optional[str] = None
    
    # Delivery
    recipients: List[str] = Field(default_factory=list)
    sent_at: Optional[datetime] = None
    delivery_attempts: int = 0
    
    class Config:
        json_encoders = {
            datetime: lambda v: v.isoformat()
        }


class MonitoringStats(BaseModel):
    """Real-time monitoring statistics."""
    total_logs: int = 0
    error_rate: float = 0.0
    avg_latency: Optional[float] = None
    active_anomalies: int = 0
    alerts_sent: int = 0
    
    # Time window
    window_start: datetime
    window_end: datetime
    
    # Resource breakdown
    by_resource_type: Dict[str, int] = Field(default_factory=dict)
    by_severity: Dict[str, int] = Field(default_factory=dict)


class SystemHealth(BaseModel):
    """System health status."""
    status: str = "healthy"
    uptime_seconds: int
    
    # Service status
    gcp_connected: bool = False
    openai_connected: bool = False
    email_service_healthy: bool = False
    
    # Buffer status
    logs_in_buffer: int = 0
    buffer_utilization: float = 0.0
    
    # Performance
    processing_rate_per_second: float = 0.0
    last_anomaly_check: Optional[datetime] = None


# Request/Response models for API

class FileUploadResponse(BaseModel):
    """Response for file upload."""
    success: bool
    message: str
    logs_processed: int
    file_size_mb: float


class GCPConfigRequest(BaseModel):
    """Request to configure GCP connection."""
    project_id: str
    service_account_path: str
    log_filter: Optional[str] = None


class GCPConfigResponse(BaseModel):
    """Response for GCP configuration."""
    success: bool
    message: str
    project_id: str
    connection_tested: bool


class AlertPreviewRequest(BaseModel):
    """Request to preview an alert before sending."""
    anomaly_id: str
    recipients: List[str]


class AlertSendRequest(BaseModel):
    """Request to send an alert."""
    alert_id: str
    recipients: List[str]
    force_send: bool = False  # Override rate limiting
