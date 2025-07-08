from typing import Any, Dict, List, Union, Optional
from datetime import datetime, timezone
import json
import logging
from app.models.log_models import RawGCPLogEntry, NormalizedLogEntry, LogValidationError, LogBufferStatus
from app.utils.error_utils import log_warning, log_and_raise
from app.utils.otel_utils import extract_correlation_context

def parse_timestamp_aware(ts):
    if not ts:
        return datetime.now(timezone.utc)
    if isinstance(ts, datetime):
        if ts.tzinfo is None:
            return ts.replace(tzinfo=timezone.utc)
        return ts
    if isinstance(ts, str):
        if ts.endswith('Z'):
            return datetime.fromisoformat(ts.replace('Z', '+00:00'))
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            return dt.replace(tzinfo=timezone.utc)
        return dt
    return datetime.now(timezone.utc)

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

    def normalize(self, raw_log):
        # Support both dict and object input
        def get_field(obj, field, default=None):
            if isinstance(obj, dict):
                return obj.get(field, default)
            return getattr(obj, field, default)

        # Ensure raw_log is a dict for NormalizedLogEntry
        raw_log_dict = raw_log.model_dump() if hasattr(raw_log, 'model_dump') else raw_log

        # Helper: get field from top level, else from raw_log
        def get_field_with_fallback(obj, field, default=None):
            val = get_field(obj, field, None)
            if val is not None:
                return val
            # Fallback: look inside 'raw_log' if present
            raw = get_field(obj, 'raw_log', {})
            if raw and isinstance(raw, dict):
                return get_field(raw, field, default)
            return default

        try:
            timestamp = get_field_with_fallback(raw_log, 'timestamp')
            timestamp = parse_timestamp_aware(timestamp)
            severity = get_field_with_fallback(raw_log, 'severity')
            resource = get_field_with_fallback(raw_log, 'resource', {})
            resource_type = None
            resource_labels = {}
            if resource:
                resource_type = get_field(resource, 'type') or get_field_with_fallback(raw_log, 'resource_type')
                resource_labels = get_field(resource, 'labels', {}) or get_field_with_fallback(raw_log, 'resource_labels', {})
            else:
                resource_type = get_field_with_fallback(raw_log, 'resource_type')
                resource_labels = get_field_with_fallback(raw_log, 'resource_labels', {})
            json_payload = get_field_with_fallback(raw_log, 'jsonPayload', {})
            message = get_field(json_payload, 'message') if json_payload else get_field_with_fallback(raw_log, 'message')
            if not message:
                message = str(raw_log)

            from app.models.log_models import NormalizedLogEntry
            normalized_log = NormalizedLogEntry(
                timestamp=timestamp,
                severity=severity,
                resource_type=resource_type,
                message=message,
                raw_log=raw_log_dict
            )
            logging.info(f"Successfully normalized log: {normalized_log}")
            return normalized_log
        except Exception as e:
            logging.error(f"Log normalization failed | Error: {e} | Raw log: {raw_log}")
            return None

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