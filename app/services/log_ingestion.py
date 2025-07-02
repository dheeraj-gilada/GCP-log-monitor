"""
Log ingestion service for parsing and normalizing different log formats.
Handles file uploads, real-time log streaming, and manages in-memory buffer.
"""

import json
import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional, Union, AsyncGenerator
from pathlib import Path
import re

from app.config import get_settings
from app.models.schemas import LogEntry, LogSeverity, LogResource, HTTPRequest, ResourceType
from app.models.gcp_models import GCPLogParser, GCPResourceExtractor
from app.api.websockets import broadcast_log_entry


class LogBuffer:
    """Thread-safe in-memory log buffer with sliding window functionality."""
    
    def __init__(self, max_size: int = 10000, window_minutes: int = 10):
        self.max_size = max_size
        self.window_minutes = window_minutes
        self.logs: deque = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
    
    async def add_log(self, log_entry: LogEntry):
        """Add a log entry to the buffer."""
        async with self._lock:
            self.logs.append(log_entry)
            await self._cleanup_old_logs()
    
    async def add_logs(self, log_entries: List[LogEntry]):
        """Add multiple log entries to the buffer."""
        async with self._lock:
            self.logs.extend(log_entries)
            await self._cleanup_old_logs()
    
    async def get_logs(self, 
                      limit: Optional[int] = None,
                      severity: Optional[LogSeverity] = None,
                      resource_type: Optional[ResourceType] = None,
                      start_time: Optional[datetime] = None,
                      end_time: Optional[datetime] = None) -> List[LogEntry]:
        """Get logs from buffer with optional filtering."""
        async with self._lock:
            filtered_logs = []
            
            for log in self.logs:
                # Apply filters
                if severity and log.severity != severity:
                    continue
                if resource_type and log.resource.type != resource_type:
                    continue
                if start_time and log.timestamp < start_time:
                    continue
                if end_time and log.timestamp > end_time:
                    continue
                
                filtered_logs.append(log)
            
            # Sort by timestamp (newest first)
            filtered_logs.sort(key=lambda x: x.timestamp, reverse=True)
            
            if limit:
                filtered_logs = filtered_logs[:limit]
            
            return filtered_logs
    
    async def get_logs_in_window(self, minutes: Optional[int] = None) -> List[LogEntry]:
        """Get logs within the specified time window."""
        window_minutes = minutes or self.window_minutes
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)
        
        return await self.get_logs(start_time=cutoff_time)
    
    async def _cleanup_old_logs(self):
        """Remove logs older than the sliding window."""
        cutoff_time = datetime.now(timezone.utc) - timedelta(minutes=self.window_minutes)
        
        # Remove old logs from the left side of deque
        while self.logs and self.logs[0].timestamp < cutoff_time:
            self.logs.popleft()
    
    async def get_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        async with self._lock:
            if not self.logs:
                return {
                    "total_logs": 0,
                    "buffer_utilization": 0.0,
                    "oldest_log": None,
                    "newest_log": None,
                    "window_start": datetime.now(timezone.utc) - timedelta(minutes=self.window_minutes),
                    "window_end": datetime.now(timezone.utc)
                }
            
            oldest_log = min(self.logs, key=lambda x: x.timestamp)
            newest_log = max(self.logs, key=lambda x: x.timestamp)
            
            return {
                "total_logs": len(self.logs),
                "buffer_utilization": len(self.logs) / self.max_size,
                "oldest_log": oldest_log.timestamp,
                "newest_log": newest_log.timestamp,
                "window_start": datetime.now(timezone.utc) - timedelta(minutes=self.window_minutes),
                "window_end": datetime.now(timezone.utc)
            }


class LogParser:
    """Parse different log formats and normalize them."""
    
    def __init__(self):
        self.gcp_parser = GCPLogParser()
        self.gcp_extractor = GCPResourceExtractor()
    
    def parse_json_log(self, log_line: str, source: str = "file") -> Optional[LogEntry]:
        """Parse a JSON log line."""
        try:
            log_data = json.loads(log_line.strip())
            return self._parse_log_data(log_data, source)
        except json.JSONDecodeError:
            return None
        except Exception as e:
            print(f"Error parsing JSON log: {e}")
            return None
    
    def parse_text_log(self, log_line: str, source: str = "file") -> Optional[LogEntry]:
        """Parse a text log line using regex patterns."""
        try:
            # Try different text log patterns
            patterns = [
                self._parse_apache_common_log,
                self._parse_nginx_log,
                self._parse_generic_text_log
            ]
            
            for pattern_func in patterns:
                result = pattern_func(log_line, source)
                if result:
                    return result
            
            # Fallback: create basic log entry
            return self._create_basic_log_entry(log_line, source)
            
        except Exception as e:
            print(f"Error parsing text log: {e}")
            return None
    
    def _parse_log_data(self, log_data: Dict[str, Any], source: str) -> LogEntry:
        """Parse structured log data (from JSON or GCP)."""
        # Determine if this is a GCP log format
        if self._is_gcp_log_format(log_data):
            return self._parse_gcp_log(log_data, source)
        else:
            return self._parse_generic_json_log(log_data, source)
    
    def _is_gcp_log_format(self, log_data: Dict[str, Any]) -> bool:
        """Check if log data matches GCP log format."""
        gcp_fields = ['timestamp', 'severity', 'resource', 'jsonPayload']
        return any(field in log_data for field in gcp_fields)
    
    def _parse_gcp_log(self, log_data: Dict[str, Any], source: str) -> LogEntry:
        """Parse GCP-specific log format."""
        # Extract basic fields
        timestamp = self._parse_timestamp(log_data.get('timestamp'))
        severity = self._parse_severity(log_data.get('severity', 'INFO'))
        message = log_data.get('textPayload') or log_data.get('jsonPayload', {}).get('message', '')
        
        # Extract resource information
        resource_type = self.gcp_extractor.extract_resource_type(log_data)
        resource_labels = self.gcp_extractor.extract_resource_labels(log_data)
        resource = LogResource(type=resource_type, labels=resource_labels)
        
        # Extract HTTP request if available
        http_request = self.gcp_extractor.extract_http_request(log_data)
        
        # Extract other fields
        json_payload = log_data.get('jsonPayload', {})
        labels = log_data.get('labels', {})
        trace = log_data.get('trace')
        span_id = log_data.get('spanId')
        
        return LogEntry(
            timestamp=timestamp,
            severity=severity,
            message=message,
            resource=resource,
            http_request=http_request,
            json_payload=json_payload,
            labels=labels,
            trace=trace,
            span_id=span_id,
            source=source,
            raw_log=json.dumps(log_data)
        )
    
    def _parse_generic_json_log(self, log_data: Dict[str, Any], source: str) -> LogEntry:
        """Parse generic JSON log format."""
        timestamp = self._parse_timestamp(
            log_data.get('timestamp') or 
            log_data.get('@timestamp') or 
            log_data.get('time') or
            datetime.utcnow().isoformat()
        )
        
        severity = self._parse_severity(
            log_data.get('level') or 
            log_data.get('severity') or 
            log_data.get('priority', 'INFO')
        )
        
        message = (
            log_data.get('message') or 
            log_data.get('msg') or 
            log_data.get('text') or
            str(log_data)
        )
        
        # Create basic resource
        resource = LogResource(
            type=ResourceType.UNKNOWN,
            labels=log_data.get('labels', {})
        )
        
        return LogEntry(
            timestamp=timestamp,
            severity=severity,
            message=message,
            resource=resource,
            json_payload=log_data,
            source=source,
            raw_log=json.dumps(log_data)
        )
    
    def _parse_apache_common_log(self, log_line: str, source: str) -> Optional[LogEntry]:
        """Parse Apache Common Log Format."""
        # Example: 127.0.0.1 - - [25/Dec/2021:10:00:00 +0000] "GET /index.html HTTP/1.1" 200 1234
        pattern = r'(\S+) \S+ \S+ \[([^\]]+)\] "(\S+) (\S+) (\S+)" (\d+) (\d+)'
        match = re.match(pattern, log_line)
        
        if not match:
            return None
        
        ip, timestamp_str, method, url, protocol, status, size = match.groups()
        
        try:
            # Parse Apache timestamp format
            timestamp = datetime.strptime(timestamp_str.split()[0], '%d/%b/%Y:%H:%M:%S')
            timestamp = timestamp.replace(tzinfo=timezone.utc)
        except:
            timestamp = datetime.utcnow()
        
        # Determine severity based on HTTP status
        status_code = int(status)
        if status_code >= 500:
            severity = LogSeverity.ERROR
        elif status_code >= 400:
            severity = LogSeverity.WARNING
        else:
            severity = LogSeverity.INFO
        
        http_request = HTTPRequest(
            status=status_code,
            method=method,
            url=url,
            remote_ip=ip
        )
        
        resource = LogResource(type=ResourceType.UNKNOWN, labels={'server_type': 'apache'})
        
        return LogEntry(
            timestamp=timestamp,
            severity=severity,
            message=f"{method} {url} {status}",
            resource=resource,
            http_request=http_request,
            source=source,
            raw_log=log_line
        )
    
    def _parse_nginx_log(self, log_line: str, source: str) -> Optional[LogEntry]:
        """Parse NGINX log format."""
        # Similar to Apache but with slight variations
        # This is a simplified version - can be extended
        return self._parse_apache_common_log(log_line, source)
    
    def _parse_generic_text_log(self, log_line: str, source: str) -> Optional[LogEntry]:
        """Parse generic text log with timestamp detection."""
        # Try to extract timestamp from beginning of line
        timestamp_patterns = [
            r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})',
            r'(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})',
            r'(\d{2}/\d{2}/\d{4} \d{2}:\d{2}:\d{2})',
        ]
        
        timestamp = datetime.utcnow()
        message = log_line
        
        for pattern in timestamp_patterns:
            match = re.search(pattern, log_line)
            if match:
                try:
                    timestamp_str = match.group(1)
                    if 'T' in timestamp_str:
                        timestamp = datetime.fromisoformat(timestamp_str.replace('T', ' '))
                    else:
                        timestamp = datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S')
                    timestamp = timestamp.replace(tzinfo=timezone.utc)
                    break
                except:
                    continue
        
        # Detect severity from keywords
        severity = LogSeverity.INFO
        log_lower = log_line.lower()
        if any(word in log_lower for word in ['error', 'exception', 'failed', 'failure']):
            severity = LogSeverity.ERROR
        elif any(word in log_lower for word in ['warning', 'warn']):
            severity = LogSeverity.WARNING
        elif any(word in log_lower for word in ['debug']):
            severity = LogSeverity.DEBUG
        
        resource = LogResource(type=ResourceType.UNKNOWN, labels={})
        
        return LogEntry(
            timestamp=timestamp,
            severity=severity,
            message=message.strip(),
            resource=resource,
            source=source,
            raw_log=log_line
        )
    
    def _create_basic_log_entry(self, log_line: str, source: str) -> LogEntry:
        """Create a basic log entry when parsing fails."""
        return LogEntry(
            timestamp=datetime.now(timezone.utc),
            severity=LogSeverity.INFO,
            message=log_line.strip(),
            resource=LogResource(type=ResourceType.UNKNOWN, labels={}),
            source=source,
            raw_log=log_line
        )
    
    def _parse_timestamp(self, timestamp_str: Union[str, None]) -> datetime:
        """Parse various timestamp formats."""
        if not timestamp_str:
            return datetime.now(timezone.utc)
        
        if isinstance(timestamp_str, datetime):
            # Ensure datetime is timezone-aware
            if timestamp_str.tzinfo is None:
                return timestamp_str.replace(tzinfo=timezone.utc)
            return timestamp_str
        
        # Try different timestamp formats
        formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%dT%H:%M:%S.%f',
            '%Y-%m-%dT%H:%M:%S',
            '%Y-%m-%d %H:%M:%S.%f',
            '%Y-%m-%d %H:%M:%S',
        ]
        
        for fmt in formats:
            try:
                dt = datetime.strptime(timestamp_str, fmt)
                # Always ensure timezone-aware datetime
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                return dt
            except ValueError:
                continue
        
        # Fallback - return current time as timezone-aware
        return datetime.now(timezone.utc)
    
    def _parse_severity(self, severity_str: str) -> LogSeverity:
        """Parse severity string to LogSeverity enum."""
        if not severity_str:
            return LogSeverity.INFO
        
        severity_mapping = {
            'emergency': LogSeverity.EMERGENCY,
            'alert': LogSeverity.ALERT,
            'critical': LogSeverity.CRITICAL,
            'crit': LogSeverity.CRITICAL,
            'error': LogSeverity.ERROR,
            'err': LogSeverity.ERROR,
            'warning': LogSeverity.WARNING,
            'warn': LogSeverity.WARNING,
            'notice': LogSeverity.NOTICE,
            'info': LogSeverity.INFO,
            'debug': LogSeverity.DEBUG,
            'trace': LogSeverity.DEBUG,
        }
        
        severity_lower = severity_str.lower()
        return severity_mapping.get(severity_lower, LogSeverity.INFO)


class LogIngestionService:
    """Main service for log ingestion and processing."""
    
    def __init__(self):
        self.settings = get_settings()
        self.buffer = LogBuffer(
            max_size=self.settings.max_buffer_size,
            window_minutes=self.settings.log_buffer_minutes
        )
        self.parser = LogParser()
        self._processing = False
    
    async def ingest_file(self, file_content: str, filename: str, log_format: str = "auto") -> Dict[str, Any]:
        """Ingest logs from uploaded file."""
        try:
            lines = file_content.strip().split('\n')
            processed_logs = []
            
            for line_num, line in enumerate(lines, 1):
                if not line.strip():
                    continue
                
                try:
                    log_entry = await self._parse_log_line(line, log_format, f"file:{filename}")
                    if log_entry:
                        processed_logs.append(log_entry)
                except Exception as e:
                    print(f"Error processing line {line_num}: {e}")
                    continue
            
            # Add logs to buffer
            if processed_logs:
                await self.buffer.add_logs(processed_logs)
                
                # Broadcast to WebSocket clients
                for log_entry in processed_logs[-10:]:  # Last 10 logs
                    log_dict = log_entry.dict()
                    # Convert datetime objects to ISO strings for JSON serialization
                    if 'timestamp' in log_dict and log_dict['timestamp']:
                        log_dict['timestamp'] = log_dict['timestamp'].isoformat()
                    await broadcast_log_entry(log_dict)
            
            return {
                "success": True,
                "logs_processed": len(processed_logs),
                "total_lines": len(lines),
                "file_size_kb": len(file_content) / 1024
            }
            
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "logs_processed": 0
            }
    
    async def ingest_real_time_log(self, log_data: Dict[str, Any], source: str = "gcp") -> bool:
        """Ingest a single log entry in real-time."""
        try:
            log_entry = self.parser._parse_log_data(log_data, source)
            await self.buffer.add_log(log_entry)
            
            # Broadcast to WebSocket clients
            log_dict = log_entry.dict()
            # Convert datetime objects to ISO strings for JSON serialization
            if 'timestamp' in log_dict and log_dict['timestamp']:
                log_dict['timestamp'] = log_dict['timestamp'].isoformat()
            await broadcast_log_entry(log_dict)
            
            return True
        except Exception as e:
            print(f"Error ingesting real-time log: {e}")
            return False
    
    async def _parse_log_line(self, line: str, log_format: str, source: str) -> Optional[LogEntry]:
        """Parse a single log line based on format."""
        if log_format == "json" or (log_format == "auto" and line.strip().startswith('{')):
            return self.parser.parse_json_log(line, source)
        else:
            return self.parser.parse_text_log(line, source)
    
    async def get_logs(self, **filters) -> List[LogEntry]:
        """Get logs from buffer with filtering."""
        return await self.buffer.get_logs(**filters)
    
    async def get_recent_logs(self, limit: int = 100) -> List[LogEntry]:
        """Get recent logs from buffer."""
        return await self.buffer.get_logs(limit=limit)
    
    async def get_logs_in_window(self, minutes: Optional[int] = None) -> List[LogEntry]:
        """Get logs within time window."""
        return await self.buffer.get_logs_in_window(minutes)
    
    async def get_buffer_stats(self) -> Dict[str, Any]:
        """Get buffer statistics."""
        return await self.buffer.get_stats()
    
    async def start_processing(self):
        """Start background processing tasks."""
        self._processing = True
        # TODO: Add background tasks for cleanup, metrics calculation, etc.
    
    async def stop_processing(self):
        """Stop background processing tasks."""
        self._processing = False
    
    def is_processing(self) -> bool:
        """Check if service is currently processing."""
        return self._processing
