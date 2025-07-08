import os
from typing import Any, Dict, List, Optional
from google.cloud import logging_v2
from google.oauth2 import service_account
from datetime import datetime, timezone
import json
from app.utils.error_utils import log_and_raise, log_warning
from app.utils.otel_utils import start_trace 
from app.models.log_models import LogBufferStatus 

class GCPService:
    """
    Handles authentication and integration with Google Cloud Logging API.
    Fetches logs for any resource type, supports flexible queries, and handles pagination.
    """
    def __init__(self, project_id: Optional[str] = None, credentials_path: Optional[str] = None):
        self.project_id = project_id or os.getenv("GCP_PROJECT_ID")
        self.credentials_path = credentials_path or os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        self.client = self._init_client()

    def _init_client(self):
        try:
            if self.credentials_path:
                credentials = service_account.Credentials.from_service_account_file(self.credentials_path)
                return logging_v2.Client(project=self.project_id, credentials=credentials)
            else:
                return logging_v2.Client(project=self.project_id)
        except Exception as e:
            log_and_raise("Failed to initialize GCP Logging client", e, {"project_id": self.project_id, "credentials_path": self.credentials_path})

    def fetch_logs(self, query_params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Fetch logs from GCP Cloud Logging API using flexible query parameters.
        query_params can include:
            - filter: str (advanced log filter)
            - order_by: str ("timestamp desc" or "timestamp asc")
            - page_size: int
            - resource_names: List[str]
            - start_time: datetime
            - end_time: datetime
        Returns a list of log entries (dicts).
        """
        filter_ = query_params.get("filter", "")
        order_by = query_params.get("order_by", "timestamp desc")
        page_size = query_params.get("page_size", 1000)
        resource_names = query_params.get("resource_names", [f"projects/{self.project_id}"])
        start_time = query_params.get("start_time")
        end_time = query_params.get("end_time")

        if start_time:
            filter_ += f" timestamp >= \"{self._to_rfc3339(start_time)}\""
        if end_time:
            filter_ += f" timestamp <= \"{self._to_rfc3339(end_time)}\""

        entries = []
        try:
            iterator = self.client.list_entries(
                filter_=filter_,
                order_by=order_by,
                page_size=page_size,
                resource_names=resource_names
            )
            for entry in iterator:
                entries.append(self._entry_to_dict(entry))
        except Exception as e:
            log_warning("Failed to fetch logs from GCP", {"error": str(e), "query_params": query_params})
        return entries

    def _entry_to_dict(self, entry) -> Dict[str, Any]:
        # Convert google.cloud.logging_v2.entries.LogEntry to dict
        try:
            return dict(entry)
        except Exception:
            # Fallback: use proto representation
            return json.loads(entry.to_api_repr())

    def _to_rfc3339(self, dt: datetime) -> str:
        # Convert datetime to RFC3339 string
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.isoformat().replace("+00:00", "Z") 