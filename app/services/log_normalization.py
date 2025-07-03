from typing import Any, Dict, List, Union, Optional
from datetime import datetime
import json
import logging
from app.models.log_models import RawGCPLogEntry, NormalizedLogEntry, LogValidationError, LogBufferStatus
from app.utils.error_utils import log_warning, log_and_raise
from app.utils.otel_utils import extract_correlation_context

class AdaptiveLogParser:
    """
    Schema-agnostic parser for GCP logs. Detects log format, normalizes fields, and handles all GCP log structure variations.
    """
    def __init__(self):
        self.logger = logging.getLogger("AdaptiveLogParser")

    def parse(self, raw_data: Union[str, List[Any], Dict[str, Any]], original_format: str = "auto") -> List[RawGCPLogEntry]:
        """
        Accepts raw log data (string, list, or dict) and returns a list of RawGCPLogEntry objects.
        Auto-detects format if needed.
        """
        logs = []
        try:
            if isinstance(raw_data, str):
                # Try to parse as JSON array or line-delimited JSON
                try:
                    data = json.loads(raw_data)
                    if isinstance(data, list):
                        logs = [RawGCPLogEntry(raw_log=entry, **entry) for entry in data]
                    elif isinstance(data, dict):
                        logs = [RawGCPLogEntry(raw_log=data, **data)]
                except Exception:
                    # Fallback: treat as line-delimited JSON
                    for line in raw_data.strip().splitlines():
                        try:
                            entry = json.loads(line)
                            logs.append(RawGCPLogEntry(raw_log=entry, **entry))
                        except Exception as e:
                            log_warning("Failed to parse line as JSON", {"error": str(e)})
            elif isinstance(raw_data, list):
                logs = [RawGCPLogEntry(raw_log=entry, **entry) for entry in raw_data]
            elif isinstance(raw_data, dict):
                logs = [RawGCPLogEntry(raw_log=raw_data, **raw_data)]
        except Exception as e:
            log_and_raise("Failed to parse raw logs", e)
        return logs

    def normalize(self, raw_log: RawGCPLogEntry) -> NormalizedLogEntry:
        """
        Converts a RawGCPLogEntry to a NormalizedLogEntry using robust heuristics.
        Handles all GCP log structure variations.
        """
        # --- Timestamp extraction ---
        timestamp = (
            raw_log.timestamp or
            self._extract_nested(raw_log.json_payload, ["timestamp"]) or
            self._extract_nested(raw_log.json_payload, ["time"]) or
            raw_log.receive_timestamp or
            datetime.utcnow()
        )
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            except Exception:
                timestamp = datetime.utcnow()

        # --- Severity extraction ---
        severity = (
            raw_log.severity or
            self._extract_nested(raw_log.json_payload, ["severity"]) or
            self._extract_nested(raw_log.json_payload, ["level"]) or
            self._extract_nested(raw_log.json_payload, ["priority"]) or
            None
        )
        if isinstance(severity, int):
            severity = self._map_numeric_severity(severity)
        elif isinstance(severity, str):
            severity = severity.upper()

        # --- Message extraction ---
        message = (
            raw_log.text_payload or
            self._extract_nested(raw_log.json_payload, ["message"]) or
            self._extract_nested(raw_log.json_payload, ["msg"]) or
            self._extract_nested(raw_log.json_payload, ["log"]) or
            self._extract_nested(raw_log.json_payload, ["event"]) or
            self._extract_nested(raw_log.proto_payload, ["methodName"]) or
            str(raw_log.raw_log)
        )

        # --- Resource extraction ---
        resource_type = None
        resource_labels = None
        if raw_log.resource:
            resource_type = raw_log.resource.get("type")
            resource_labels = raw_log.resource.get("labels")

        # --- Correlation context (trace/span) ---
        correlation_context = extract_correlation_context(raw_log)

        # --- Build NormalizedLogEntry ---
        return NormalizedLogEntry(
            timestamp=timestamp,
            message=message,
            severity=severity,
            resource_type=resource_type,
            resource_labels=resource_labels,
            correlation_context=correlation_context,
            raw_log=raw_log.raw_log
        )

    def _extract_nested(self, obj: Optional[Dict[str, Any]], keys: List[str]) -> Optional[Any]:
        if not obj:
            return None
        for key in keys:
            if key in obj:
                return obj[key]
        return None

    def _map_numeric_severity(self, value: int) -> str:
        # Map numeric severity to string (GCP uses syslog levels)
        mapping = {
            0: "EMERGENCY", 1: "ALERT", 2: "CRITICAL", 3: "ERROR", 4: "WARNING",
            5: "NOTICE", 6: "INFO", 7: "DEBUG"
        }
        return mapping.get(value, str(value)) 