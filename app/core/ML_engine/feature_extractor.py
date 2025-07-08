import re
from typing import Dict, Any
import numpy as np

class FeatureExtractor:
    """
    Extracts features from normalized logs for ML models.
    Uses type-specific feature selection for each log type.
    """
    SEVERITY_MAP = {
        "DEFAULT": 0, "DEBUG": 100, "INFO": 200, "NOTICE": 300, "WARNING": 400,
        "ERROR": 500, "CRITICAL": 600, "ALERT": 700, "EMERGENCY": 800
    }
    IMPUTED = {
        'latency_ms': 100,
        'status_code': 200,
        'hour': 12,
        'day_of_week': 3,
    }
    def __init__(self):
        self.cat_maps = {}

    def label_encode(self, key, value):
        if key not in self.cat_maps:
            self.cat_maps[key] = {}
        if value not in self.cat_maps[key]:
            self.cat_maps[key][value] = len(self.cat_maps[key]) + 1
        return self.cat_maps[key][value]

    def extract_features(self, log: Dict[str, Any]) -> Dict[str, Any]:
        features = {}
        # Detect log type
        resource = log.get("raw_log", {}).get("resource", {}) or log.get("resource", {})
        resource_type = resource.get("type") or log.get("resource_type")
        finding = log.get("raw_log", {}).get("finding", {}) or log.get("finding", {})
        # Common helpers
        def get_severity_num():
            sev = log.get("severity") or finding.get("severity") or "INFO"
            return self.SEVERITY_MAP.get(str(sev).upper(), 200)
        def get_message_length():
            msg = log.get("message") or log.get("jsonPayload", {}).get("message") or ""
            return len(msg)
        def get_hour_and_dow(ts=None):
            from datetime import datetime
            ts = ts or log.get("timestamp") or finding.get("eventTime")
            if ts:
                try:
                    dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
                    return dt.hour, dt.weekday()
                except Exception:
                    pass
            return self.IMPUTED['hour'], self.IMPUTED['day_of_week']
        # Type-specific extraction (minimal, anomaly-focused)
        if resource_type == "gce_instance":
            features["severity_num"] = get_severity_num()
            features["message_length"] = get_message_length()
            # Only keep error_code/component if value set is small/meaningful
            err_code = log.get("jsonPayload", {}).get("error_code", "none")
            features["error_code"] = self.label_encode("error_code", err_code)
            comp = log.get("jsonPayload", {}).get("component", "none")
            features["component"] = self.label_encode("component", comp)
            hour, dow = get_hour_and_dow()
            features["hour"] = hour
            features["day_of_week"] = dow
        elif resource_type == "cloud_function":
            features["severity_num"] = get_severity_num()
            features["message_length"] = get_message_length()
            http_req = log.get("raw_log", {}).get("httpRequest", {}) or log.get("httpRequest", {})
            status = http_req.get("status", self.IMPUTED['status_code'])
            try:
                features["status_code"] = int(status) if status is not None else self.IMPUTED['status_code']
            except Exception:
                features["status_code"] = self.IMPUTED['status_code']
            latency = http_req.get("latency")
            if latency:
                m = re.match(r"([0-9.]+)s", latency)
                features["latency_ms"] = float(m.group(1)) * 1000 if m else self.IMPUTED['latency_ms']
            else:
                features["latency_ms"] = self.IMPUTED['latency_ms']
            hour, dow = get_hour_and_dow()
            features["hour"] = hour
            features["day_of_week"] = dow
        elif resource_type in ["cloud_sql", "cloud_storage", "kubernetes_engine", "network", "cloud_identity", "security_command_center"]:
            features["severity_num"] = get_severity_num()
            features["message_length"] = get_message_length()
            # Try to extract status_code and latency_ms if present
            http_req = log.get("raw_log", {}).get("httpRequest", {}) or log.get("httpRequest", {})
            status = http_req.get("status")
            if status is not None:
                try:
                    features["status_code"] = int(status)
                except Exception:
                    pass
            latency = http_req.get("latency")
            if latency:
                m = re.match(r"([0-9.]+)s", latency)
                features["latency_ms"] = float(m.group(1)) * 1000 if m else self.IMPUTED['latency_ms']
            # error_code if present and meaningful
            err_code = log.get("jsonPayload", {}).get("error_code")
            if err_code:
                features["error_code"] = self.label_encode("error_code", err_code)
            hour, dow = get_hour_and_dow()
            features["hour"] = hour
            features["day_of_week"] = dow
        elif finding:
            sev = finding.get("severity", "LOW")
            features["severity_num"] = self.SEVERITY_MAP.get(str(sev).upper(), 100)
            cat = finding.get("category", "unknown")
            features["category"] = self.label_encode("category", cat)
            fclass = finding.get("findingClass", "unknown")
            features["findingClass"] = self.label_encode("findingClass", fclass)
            hour, dow = get_hour_and_dow(finding.get("eventTime"))
            features["hour"] = hour
            features["day_of_week"] = dow
        else:
            # Generic fallback for unknown types
            features["severity_num"] = get_severity_num()
            features["message_length"] = get_message_length()
            # Try to extract latency_ms if present
            raw_log = log.get("raw_log", {})
            http_req = raw_log.get("httpRequest", {}) or log.get("httpRequest", {})
            latency = http_req.get("latency")
            if latency:
                m = re.match(r"([0-9.]+)s", latency)
                features["latency_ms"] = float(m.group(1)) * 1000 if m else self.IMPUTED['latency_ms']
            else:
                features["latency_ms"] = self.IMPUTED['latency_ms']
            hour, dow = get_hour_and_dow()
            features["hour"] = hour
            features["day_of_week"] = dow
        return features 