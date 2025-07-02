"""
GCP Service for connecting to Google Cloud Logging and fetching logs.
Supports real-time log streaming and resource-specific log fetching.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, AsyncGenerator, Callable
from google.cloud import logging as gcp_logging
from google.auth.exceptions import DefaultCredentialsError
import json
import os

from app.config import get_settings
from app.models.schemas import LogEntry, LogSeverity, ResourceType
from app.models.gcp_models import GCPLogParser, GCPResourceExtractor
from app.core.metrics_calculator import MetricsCalculator


class GCPLogStreamConfig:
    """Configuration for GCP log streaming."""
    
    def __init__(self,
                 resource_types: List[ResourceType] = None,
                 severity_filter: Optional[LogSeverity] = None,
                 time_window_minutes: int = 10,
                 max_entries: int = 1000,
                 project_id: Optional[str] = None,
                 custom_filter: Optional[str] = None):
        self.resource_types = resource_types or [ResourceType.CLOUD_SQL, ResourceType.COMPUTE_ENGINE]
        self.severity_filter = severity_filter
        self.time_window_minutes = time_window_minutes
        self.max_entries = max_entries
        self.project_id = project_id
        self.custom_filter = custom_filter


class GCPService:
    """Service for interacting with Google Cloud Logging."""
    
    def __init__(self):
        self.settings = get_settings()
        self.client = None
        self.parser = GCPLogParser()
        self.extractor = GCPResourceExtractor()
        self.metrics_calculator = MetricsCalculator()
        self._streaming = False
        self._stream_config: Optional[GCPLogStreamConfig] = None
        self._log_callback: Optional[Callable] = None
        
        # Initialize GCP client
        self._initialize_client()
    
    def _initialize_client(self):
        """Initialize the GCP Logging client."""
        try:
            # Use service account credentials if provided
            if self.settings.gcp_service_account_path:
                self.client = gcp_logging.Client.from_service_account_json(
                    self.settings.gcp_service_account_path,
                    project=self.settings.gcp_project_id
                )
            else:
                # Use default credentials (ADC)
                self.client = gcp_logging.Client(project=self.settings.gcp_project_id)
            
            logging.info(f"GCP Logging client initialized for project: {self.settings.gcp_project_id}")
            
        except DefaultCredentialsError as e:
            logging.error(f"GCP credentials not found: {e}")
            self.client = None
        except Exception as e:
            logging.error(f"Failed to initialize GCP client: {e}")
            self.client = None
    
    def is_connected(self) -> bool:
        """Check if GCP client is properly initialized."""
        return self.client is not None
    
    async def test_connection(self) -> Dict[str, Any]:
        """Test GCP connection and return status."""
        if not self.client:
            return {
                "connected": False,
                "error": "GCP client not initialized",
                "project_id": None
            }
        
        try:
            # Try to list a few log entries to test the connection
            entries = list(self.client.list_entries(
                max_results=1,
                page_size=1
            ))
            
            return {
                "connected": True,
                "project_id": self.settings.gcp_project_id,
                "test_entries_count": len(entries)
            }
            
        except Exception as e:
            return {
                "connected": False,
                "error": str(e),
                "project_id": self.settings.gcp_project_id
            }
    
    async def fetch_logs(self,
                        resource_types: List[ResourceType] = None,
                        severity_filter: Optional[LogSeverity] = None,
                        start_time: Optional[datetime] = None,
                        end_time: Optional[datetime] = None,
                        max_entries: int = 1000,
                        custom_filter: Optional[str] = None) -> List[LogEntry]:
        """Fetch logs from GCP with filtering."""
        
        if not self.client:
            raise Exception("GCP client not initialized")
        
        try:
            # Build filter string
            filter_parts = []
            
            # Time range filter
            if start_time:
                filter_parts.append(f'timestamp >= "{start_time.isoformat()}"')
            if end_time:
                filter_parts.append(f'timestamp <= "{end_time.isoformat()}"')
            
            # Resource type filter
            if resource_types:
                resource_filters = []
                for resource_type in resource_types:
                    gcp_resource = self._map_resource_type_to_gcp(resource_type)
                    if gcp_resource:
                        resource_filters.append(f'resource.type="{gcp_resource}"')
                
                if resource_filters:
                    filter_parts.append(f'({" OR ".join(resource_filters)})')
            
            # Severity filter
            if severity_filter:
                gcp_severity = self._map_severity_to_gcp(severity_filter)
                filter_parts.append(f'severity >= {gcp_severity}')
            
            # Custom filter
            if custom_filter:
                filter_parts.append(custom_filter)
            
            # Combine filters
            filter_string = " AND ".join(filter_parts) if filter_parts else None
            
            logging.info(f"Fetching GCP logs with filter: {filter_string}")
            
            # Fetch logs
            entries = self.client.list_entries(
                filter_=filter_string,
                order_by=gcp_logging.DESCENDING,
                max_results=max_entries
            )
            
            # Parse entries
            log_entries = []
            for entry in entries:
                try:
                    log_entry = self._parse_gcp_entry(entry)
                    log_entries.append(log_entry)
                except Exception as e:
                    logging.warning(f"Failed to parse GCP log entry: {e}")
                    continue
            
            logging.info(f"Fetched {len(log_entries)} log entries from GCP")
            return log_entries
            
        except Exception as e:
            logging.error(f"Error fetching GCP logs: {e}")
            raise
    
    async def fetch_recent_logs(self,
                               resource_types: List[ResourceType] = None,
                               minutes: int = 10,
                               max_entries: int = 500) -> List[LogEntry]:
        """Fetch recent logs from the last N minutes."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(minutes=minutes)
        
        return await self.fetch_logs(
            resource_types=resource_types,
            start_time=start_time,
            end_time=end_time,
            max_entries=max_entries
        )
    
    async def fetch_error_logs(self,
                              resource_types: List[ResourceType] = None,
                              hours: int = 1,
                              max_entries: int = 100) -> List[LogEntry]:
        """Fetch error logs from the last N hours."""
        end_time = datetime.utcnow()
        start_time = end_time - timedelta(hours=hours)
        
        return await self.fetch_logs(
            resource_types=resource_types,
            severity_filter=LogSeverity.ERROR,
            start_time=start_time,
            end_time=end_time,
            max_entries=max_entries
        )
    
    async def start_log_streaming(self,
                                 config: GCPLogStreamConfig,
                                 log_callback: Callable[[LogEntry], None]):
        """Start real-time log streaming from GCP."""
        if not self.client:
            raise Exception("GCP client not initialized")
        
        if self._streaming:
            await self.stop_log_streaming()
        
        self._streaming = True
        self._stream_config = config
        self._log_callback = log_callback
        
        # Start streaming in background task
        asyncio.create_task(self._stream_logs())
        
        logging.info("Started GCP log streaming")
    
    async def stop_log_streaming(self):
        """Stop real-time log streaming."""
        self._streaming = False
        self._stream_config = None
        self._log_callback = None
        
        logging.info("Stopped GCP log streaming")
    
    async def _stream_logs(self):
        """Background task for streaming logs."""
        if not self._stream_config or not self._log_callback:
            return
        
        last_timestamp = datetime.utcnow()
        poll_interval = 30  # seconds
        
        while self._streaming:
            try:
                # Fetch logs since last poll
                new_logs = await self.fetch_logs(
                    resource_types=self._stream_config.resource_types,
                    severity_filter=self._stream_config.severity_filter,
                    start_time=last_timestamp,
                    max_entries=self._stream_config.max_entries,
                    custom_filter=self._stream_config.custom_filter
                )
                
                # Process new logs
                for log_entry in reversed(new_logs):  # Process in chronological order
                    if log_entry.timestamp > last_timestamp:
                        await self._log_callback(log_entry)
                        last_timestamp = max(last_timestamp, log_entry.timestamp)
                
                # Wait before next poll
                await asyncio.sleep(poll_interval)
                
            except Exception as e:
                logging.error(f"Error in log streaming: {e}")
                await asyncio.sleep(poll_interval)
    
    def _parse_gcp_entry(self, entry) -> LogEntry:
        """Parse a GCP log entry into our LogEntry model."""
        try:
            # Convert GCP entry to dict format
            entry_dict = {
                'timestamp': entry.timestamp.isoformat() if entry.timestamp else datetime.utcnow().isoformat(),
                'severity': entry.severity,
                'textPayload': getattr(entry, 'payload', None) if isinstance(getattr(entry, 'payload', None), str) else None,
                'jsonPayload': getattr(entry, 'payload', None) if isinstance(getattr(entry, 'payload', None), dict) else {},
                'resource': {
                    'type': entry.resource.type if entry.resource else 'unknown',
                    'labels': dict(entry.resource.labels) if entry.resource and entry.resource.labels else {}
                },
                'labels': dict(entry.labels) if entry.labels else {},
                'httpRequest': entry.http_request._pb if hasattr(entry, 'http_request') and entry.http_request else None,
                'trace': entry.trace,
                'spanId': entry.span_id
            }
            
            # Use the log parser to create LogEntry
            return self.parser.parse_gcp_log(entry_dict, "gcp")
            
        except Exception as e:
            logging.warning(f"Failed to parse GCP entry: {e}")
            # Fallback: create basic log entry
            return LogEntry(
                timestamp=entry.timestamp if entry.timestamp else datetime.utcnow(),
                severity=self._parse_severity(entry.severity),
                message=str(getattr(entry, 'payload', '')),
                source="gcp",
                raw_log=str(entry)
            )
    
    def _map_resource_type_to_gcp(self, resource_type: ResourceType) -> Optional[str]:
        """Map our ResourceType enum to GCP resource type strings."""
        mapping = {
            ResourceType.CLOUD_SQL: "cloudsql_database",
            ResourceType.COMPUTE_ENGINE: "gce_instance",
            ResourceType.PUBSUB: "pubsub_topic",
            ResourceType.CLOUD_FUNCTION: "cloud_function",
            ResourceType.APP_ENGINE: "gae_app",
            ResourceType.KUBERNETES: "k8s_container",
            ResourceType.LOAD_BALANCER: "http_load_balancer"
        }
        return mapping.get(resource_type)
    
    def _map_severity_to_gcp(self, severity: LogSeverity) -> str:
        """Map our LogSeverity enum to GCP severity levels."""
        mapping = {
            LogSeverity.EMERGENCY: "EMERGENCY",
            LogSeverity.ALERT: "ALERT", 
            LogSeverity.CRITICAL: "CRITICAL",
            LogSeverity.ERROR: "ERROR",
            LogSeverity.WARNING: "WARNING",
            LogSeverity.NOTICE: "NOTICE",
            LogSeverity.INFO: "INFO",
            LogSeverity.DEBUG: "DEBUG"
        }
        return mapping.get(severity, "INFO")
    
    def _parse_severity(self, gcp_severity: str) -> LogSeverity:
        """Parse GCP severity string to our LogSeverity enum."""
        mapping = {
            "EMERGENCY": LogSeverity.EMERGENCY,
            "ALERT": LogSeverity.ALERT,
            "CRITICAL": LogSeverity.CRITICAL,
            "ERROR": LogSeverity.ERROR,
            "WARNING": LogSeverity.WARNING,
            "NOTICE": LogSeverity.NOTICE,
            "INFO": LogSeverity.INFO,
            "DEBUG": LogSeverity.DEBUG
        }
        return mapping.get(gcp_severity, LogSeverity.INFO)
    
    async def get_available_resources(self) -> List[Dict[str, Any]]:
        """Get list of available GCP resources that can be monitored."""
        if not self.client:
            return []
        
        try:
            # Query for unique resource types in recent logs
            recent_time = datetime.utcnow() - timedelta(hours=24)
            filter_string = f'timestamp >= "{recent_time.isoformat()}"'
            
            entries = self.client.list_entries(
                filter_=filter_string,
                max_results=1000
            )
            
            resources = set()
            for entry in entries:
                if entry.resource:
                    resources.add((entry.resource.type, json.dumps(entry.resource.labels, sort_keys=True)))
            
            # Convert to list of dicts
            resource_list = []
            for resource_type, labels_json in resources:
                resource_list.append({
                    "type": resource_type,
                    "labels": json.loads(labels_json)
                })
            
            return resource_list
            
        except Exception as e:
            logging.error(f"Error getting available resources: {e}")
            return []
    
    async def get_log_metrics(self,
                             resource_types: List[ResourceType] = None,
                             hours: int = 1) -> Dict[str, Any]:
        """Get aggregated log metrics for the specified time period."""
        if not self.client:
            return {}
        
        try:
            end_time = datetime.utcnow()
            start_time = end_time - timedelta(hours=hours)
            
            # Fetch logs for the time period
            logs = await self.fetch_logs(
                resource_types=resource_types,
                start_time=start_time,
                end_time=end_time,
                max_entries=5000
            )
            
            # Use MetricsCalculator for all calculations
            error_rate_metrics = self.metrics_calculator.calculate_error_rate(logs)
            resource_metrics = self.metrics_calculator.calculate_resource_metrics(logs)
            volume_metrics = self.metrics_calculator.calculate_volume_metrics(logs, window_minutes=hours * 60)
            time_window_stats = self.metrics_calculator.calculate_time_window_stats(logs)
            
            # Extract specific counts for backward compatibility
            warning_logs = len([log for log in logs if log.severity == LogSeverity.WARNING])
            
            return {
                "time_period_hours": hours,
                "total_logs": error_rate_metrics["total_logs"],
                "error_logs": error_rate_metrics["error_logs"],
                "warning_logs": warning_logs,
                "error_rate": error_rate_metrics["error_rate"],
                "warning_rate": warning_logs / error_rate_metrics["total_logs"] if error_rate_metrics["total_logs"] > 0 else 0,
                "resource_metrics": resource_metrics,
                "volume_metrics": volume_metrics,
                "severity_distribution": error_rate_metrics["severity_distribution"],
                "time_window_stats": time_window_stats,
                "start_time": start_time,
                "end_time": end_time
            }
            
        except Exception as e:
            logging.error(f"Error calculating log metrics: {e}")
            return {}
    
    def is_streaming(self) -> bool:
        """Check if log streaming is currently active."""
        return self._streaming
