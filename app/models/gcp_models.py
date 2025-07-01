"""
GCP-specific data models for different log types.
Handles Cloud SQL, Compute Engine, Pub/Sub, and other GCP service logs.
"""

from datetime import datetime
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator

from app.models.schemas import LogEntry, LogSeverity, ResourceType, HTTPRequest


class CloudSQLLogEntry(BaseModel):
    """Cloud SQL specific log structure."""
    database_id: str
    instance_id: str
    
    # Performance metrics
    query_duration_ms: Optional[float] = None
    rows_examined: Optional[int] = None
    rows_sent: Optional[int] = None
    
    # Connection info
    connection_id: Optional[str] = None
    user: Optional[str] = None
    host: Optional[str] = None
    
    # Query details
    query_text: Optional[str] = None
    query_type: Optional[str] = None  # SELECT, INSERT, UPDATE, DELETE
    
    # Error details
    error_code: Optional[int] = None
    error_message: Optional[str] = None


class ComputeEngineLogEntry(BaseModel):
    """Compute Engine (GCE) specific log structure."""
    instance_id: str
    instance_name: str
    zone: str
    machine_type: str
    
    # System metrics
    cpu_utilization: Optional[float] = None
    memory_utilization: Optional[float] = None
    disk_utilization: Optional[float] = None
    
    # Network
    network_bytes_sent: Optional[int] = None
    network_bytes_received: Optional[int] = None
    
    # Process info
    process_name: Optional[str] = None
    process_id: Optional[int] = None
    
    # VM lifecycle
    operation: Optional[str] = None  # start, stop, restart, terminate


class PubSubLogEntry(BaseModel):
    """Pub/Sub specific log structure."""
    topic_name: str
    subscription_name: Optional[str] = None
    
    # Message metrics
    message_id: Optional[str] = None
    message_size_bytes: Optional[int] = None
    publish_timestamp: Optional[datetime] = None
    ack_timestamp: Optional[datetime] = None
    
    # Processing
    delivery_attempt: Optional[int] = None
    processing_duration_ms: Optional[float] = None
    
    # Errors
    error_type: Optional[str] = None  # publish_error, delivery_error, ack_timeout
    retry_count: Optional[int] = None
    
    # Attributes
    message_attributes: Dict[str, str] = Field(default_factory=dict)


class KubernetesLogEntry(BaseModel):
    """Kubernetes/GKE specific log structure."""
    cluster_name: str
    namespace: str
    pod_name: str
    container_name: str
    
    # Pod info
    node_name: Optional[str] = None
    pod_phase: Optional[str] = None
    
    # Container metrics
    cpu_request: Optional[str] = None
    memory_request: Optional[str] = None
    cpu_limit: Optional[str] = None
    memory_limit: Optional[str] = None
    
    # Labels and annotations
    pod_labels: Dict[str, str] = Field(default_factory=dict)
    annotations: Dict[str, str] = Field(default_factory=dict)


class CloudFunctionLogEntry(BaseModel):
    """Cloud Functions specific log structure."""
    function_name: str
    execution_id: str
    
    # Execution metrics
    duration_ms: Optional[float] = None
    memory_used_mb: Optional[float] = None
    
    # Trigger info
    trigger_type: Optional[str] = None  # http, pubsub, storage, etc.
    trigger_source: Optional[str] = None
    
    # Cold start
    is_cold_start: Optional[bool] = None
    
    # Error details
    function_error_type: Optional[str] = None
    stack_trace: Optional[str] = None


class GCPLogParser:
    """Parser for different GCP log formats."""
    
    @staticmethod
    def parse_cloudsql_log(raw_log: Dict[str, Any]) -> CloudSQLLogEntry:
        """Parse Cloud SQL log entry."""
        # Extract jsonPayload for Cloud SQL specific fields
        json_payload = raw_log.get('jsonPayload', {})
        
        return CloudSQLLogEntry(
            database_id=json_payload.get('databaseId', 'unknown'),
            instance_id=raw_log.get('resource', {}).get('labels', {}).get('database_id', 'unknown'),
            query_duration_ms=json_payload.get('queryDurationMs'),
            rows_examined=json_payload.get('rowsExamined'),
            rows_sent=json_payload.get('rowsSent'),
            connection_id=json_payload.get('connectionId'),
            user=json_payload.get('user'),
            host=json_payload.get('host'),
            query_text=json_payload.get('queryText'),
            query_type=json_payload.get('queryType'),
            error_code=json_payload.get('errorCode'),
            error_message=json_payload.get('errorMessage')
        )
    
    @staticmethod
    def parse_compute_log(raw_log: Dict[str, Any]) -> ComputeEngineLogEntry:
        """Parse Compute Engine log entry."""
        resource_labels = raw_log.get('resource', {}).get('labels', {})
        json_payload = raw_log.get('jsonPayload', {})
        
        return ComputeEngineLogEntry(
            instance_id=resource_labels.get('instance_id', 'unknown'),
            instance_name=resource_labels.get('instance_name', 'unknown'),
            zone=resource_labels.get('zone', 'unknown'),
            machine_type=resource_labels.get('machine_type', 'unknown'),
            cpu_utilization=json_payload.get('cpuUtilization'),
            memory_utilization=json_payload.get('memoryUtilization'),
            disk_utilization=json_payload.get('diskUtilization'),
            network_bytes_sent=json_payload.get('networkBytesSent'),
            network_bytes_received=json_payload.get('networkBytesReceived'),
            process_name=json_payload.get('processName'),
            process_id=json_payload.get('processId'),
            operation=json_payload.get('operation')
        )
    
    @staticmethod
    def parse_pubsub_log(raw_log: Dict[str, Any]) -> PubSubLogEntry:
        """Parse Pub/Sub log entry."""
        resource_labels = raw_log.get('resource', {}).get('labels', {})
        json_payload = raw_log.get('jsonPayload', {})
        
        # Parse timestamps
        publish_timestamp = None
        ack_timestamp = None
        
        if json_payload.get('publishTimestamp'):
            publish_timestamp = datetime.fromisoformat(
                json_payload['publishTimestamp'].replace('Z', '+00:00')
            )
        
        if json_payload.get('ackTimestamp'):
            ack_timestamp = datetime.fromisoformat(
                json_payload['ackTimestamp'].replace('Z', '+00:00')
            )
        
        return PubSubLogEntry(
            topic_name=resource_labels.get('topic_name', 'unknown'),
            subscription_name=resource_labels.get('subscription_name'),
            message_id=json_payload.get('messageId'),
            message_size_bytes=json_payload.get('messageSizeBytes'),
            publish_timestamp=publish_timestamp,
            ack_timestamp=ack_timestamp,
            delivery_attempt=json_payload.get('deliveryAttempt'),
            processing_duration_ms=json_payload.get('processingDurationMs'),
            error_type=json_payload.get('errorType'),
            retry_count=json_payload.get('retryCount'),
            message_attributes=json_payload.get('messageAttributes', {})
        )


class GCPResourceExtractor:
    """Extract resource information from GCP logs."""
    
    @staticmethod
    def extract_resource_type(raw_log: Dict[str, Any]) -> ResourceType:
        """Determine resource type from log structure."""
        resource = raw_log.get('resource', {})
        resource_type = resource.get('type', '')
        
        # Map GCP resource types to our enum
        type_mapping = {
            'cloudsql_database': ResourceType.CLOUDSQL_DATABASE,
            'gce_instance': ResourceType.GCE_INSTANCE,
            'pubsub_topic': ResourceType.PUBSUB_TOPIC,
            'pubsub_subscription': ResourceType.PUBSUB_SUBSCRIPTION,
            'k8s_container': ResourceType.K8S_CONTAINER,
            'cloud_function': ResourceType.CLOUD_FUNCTION,
        }
        
        return type_mapping.get(resource_type, ResourceType.UNKNOWN)
    
    @staticmethod
    def extract_resource_labels(raw_log: Dict[str, Any]) -> Dict[str, str]:
        """Extract resource labels from GCP log."""
        return raw_log.get('resource', {}).get('labels', {})
    
    @staticmethod
    def extract_http_request(raw_log: Dict[str, Any]) -> Optional[HTTPRequest]:
        """Extract HTTP request information if available."""
        http_req = raw_log.get('httpRequest')
        if not http_req:
            return None
        
        # Convert latency from duration string to float (seconds)
        latency = None
        if http_req.get('latency'):
            latency_str = http_req['latency']
            if latency_str.endswith('s'):
                try:
                    latency = float(latency_str[:-1])
                except ValueError:
                    pass
        
        return HTTPRequest(
            status=http_req.get('status'),
            latency=latency,
            method=http_req.get('requestMethod'),
            url=http_req.get('requestUrl'),
            user_agent=http_req.get('userAgent'),
            remote_ip=http_req.get('remoteIp')
        )
