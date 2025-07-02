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
from app.core.log_parser import LogParser
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
