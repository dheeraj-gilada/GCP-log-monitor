from typing import Optional, Dict, Any
from threading import Lock
from datetime import datetime, timezone
import logging
from app.models.metrics_models import IngestionMetrics, ExporterMetrics, SystemResourceMetrics, MetricsSnapshot
from app.models.log_models import LogBufferStatus
from app.utils.error_utils import log_and_raise, log_warning
from app.utils.otel_utils import start_trace

class MetricsService:
    """
    Collects and aggregates metrics for log ingestion, processing, exporting, and system observability.
    Thread-safe and designed for integration with API/status endpoints.
    """
    def __init__(self):
        self.ingestion_metrics = IngestionMetrics()
        self.exporter_metrics: Dict[str, ExporterMetrics] = {}
        self.system_metrics = SystemResourceMetrics()
        self.custom_metrics: Dict[str, Any] = {}
        self.lock = Lock()
        self.logger = logging.getLogger("MetricsService")

    def record(self, metrics: IngestionMetrics):
        """
        Update/aggregate ingestion metrics (thread-safe).
        """
        with self.lock:
            self.ingestion_metrics = metrics

    def record_exporter(self, name: str, metrics: ExporterMetrics):
        """
        Update/aggregate exporter metrics by name (thread-safe).
        """
        with self.lock:
            self.exporter_metrics[name] = metrics

    def record_system(self, metrics: SystemResourceMetrics):
        """
        Update system resource metrics (thread-safe).
        """
        with self.lock:
            self.system_metrics = metrics

    def record_custom(self, key: str, value: Any):
        """
        Record a custom metric (thread-safe).
        """
        with self.lock:
            self.custom_metrics[key] = value

    def get_snapshot(self) -> MetricsSnapshot:
        """
        Return a snapshot of all metrics for API/status endpoints.
        """
        with self.lock:
            return MetricsSnapshot(
                ingestion_metrics=self.ingestion_metrics,
                exporter_metrics=self.exporter_metrics.copy(),
                system_metrics=self.system_metrics,
                custom_metrics=self.custom_metrics.copy(),
                snapshot_time=datetime.now(timezone.utc)
            )

    # Optional: Integrate with OpenTelemetry metrics here (stub for now)
    def export_to_otel(self):
        pass 