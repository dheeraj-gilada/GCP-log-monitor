from typing import List, Optional, Dict, Any, Callable
from datetime import datetime
from app.models.log_models import (
    RawGCPLogEntry, NormalizedLogEntry, IngestionMetadata, IngestionResult, LogValidationError, IngestionRequest, IngestionResponse, LogBufferStatus
)
from app.models.metrics_models import IngestionMetrics
from app.utils.otel_utils import start_trace, set_correlation_context
from app.utils.buffer_utils import LogBuffer
from app.utils.error_utils import log_and_raise, log_warning
from app.utils.file_utils import read_file

class AdaptiveLogIngestion:
    """
    Production-ready adaptive log ingestion engine for GCP and file-based logs.
    Handles real-time streaming and batch/file upload, integrates with OpenTelemetry,
    and buffers logs for downstream processing.
    """
    def __init__(
        self,
        parser: Callable,  # AdaptiveLogParser instance
        gcp_service: Optional[Any] = None,  # GCPService instance
        metrics_service: Optional[Any] = None,  # MetricsService instance
        buffer_max_size: int = 10000
    ):
        self.parser = parser
        self.gcp_service = gcp_service
        self.metrics_service = metrics_service
        self.buffer = LogBuffer(max_size=buffer_max_size)
        self.buffer_max_size = buffer_max_size
        self.metrics = IngestionMetrics()

    def ingest_from_file(self, file_path: str, source: str = "file_upload", original_format: str = "auto") -> IngestionResult:
        """
        Ingest logs from a file (JSON or text). Returns an IngestionResult.
        """
        try:
            raw_data = read_file(file_path)
            logs = self.parser.parse(raw_data, original_format=original_format)
            return self._process_logs(logs, source=source, original_format=original_format)
        except Exception as e:
            log_and_raise("File ingestion failed", e, {"file_path": file_path})
            return IngestionResult(success=False, processed_count=0, failed_count=0, validation_errors=[LogValidationError(field="file", error_type="ingestion_error", message=str(e), raw_value=file_path)], processing_time_ms=0)

    def ingest_from_gcp(self, query_params: Dict[str, Any], source: str = "gcp_api", original_format: str = "gcp_json") -> IngestionResult:
        """
        Ingest logs from GCP Logging API using the provided query parameters.
        """
        if not self.gcp_service:
            log_and_raise("GCP service not configured")
        try:
            raw_logs = self.gcp_service.fetch_logs(query_params)
            logs = self.parser.parse(raw_logs, original_format=original_format)
            return self._process_logs(logs, source=source, original_format=original_format)
        except Exception as e:
            log_and_raise("GCP ingestion failed", e, {"query_params": query_params})
            return IngestionResult(success=False, processed_count=0, failed_count=0, validation_errors=[LogValidationError(field="gcp", error_type="ingestion_error", message=str(e), raw_value=query_params)], processing_time_ms=0)

    def ingest_stream(self, logs: List[Dict[str, Any]], source: str = "stream", original_format: str = "auto") -> IngestionResult:
        """
        Ingest logs from a real-time stream (e.g., API POST body).
        """
        try:
            parsed_logs = self.parser.parse(logs, original_format=original_format)
            return self._process_logs(parsed_logs, source=source, original_format=original_format)
        except Exception as e:
            log_and_raise("Stream ingestion failed", e, {"logs": logs})
            return IngestionResult(success=False, processed_count=0, failed_count=0, validation_errors=[LogValidationError(field="stream", error_type="ingestion_error", message=str(e), raw_value=logs)], processing_time_ms=0)

    def _process_logs(self, logs: List[RawGCPLogEntry], source: str, original_format: str) -> IngestionResult:
        """
        Normalize, buffer, and collect metrics for ingested logs.
        """
        start_time = datetime.utcnow()
        normalized_logs = []
        validation_errors = []
        processed_count = 0
        failed_count = 0
        for raw_log in logs:
            try:
                # OpenTelemetry tracing/correlation
                with start_trace("log_ingest") as span:
                    set_correlation_context(span, raw_log)
                    normalized = self.parser.normalize(raw_log)
                    normalized_logs.append(normalized)
                    self.buffer.add_log(normalized)
                    processed_count += 1
            except Exception as e:
                log_warning("Log normalization failed", {"error": str(e), "raw_log": getattr(raw_log, 'raw_log', raw_log)})
                validation_errors.append(LogValidationError(field="log", error_type="normalization_error", message=str(e), raw_value=getattr(raw_log, 'raw_log', raw_log)))
                failed_count += 1
        end_time = datetime.utcnow()
        processing_time_ms = (end_time - start_time).total_seconds() * 1000
        # Update metrics
        self.metrics.logs_received += len(logs)
        self.metrics.logs_processed += processed_count
        self.metrics.logs_failed += failed_count
        self.metrics.avg_processing_time_ms = processing_time_ms / max(1, len(logs))
        self.metrics.buffer_utilization = self.buffer.stats()["utilization"]
        if self.metrics_service:
            self.metrics_service.record(self.metrics)
        return IngestionResult(
            success=failed_count == 0,
            processed_count=processed_count,
            failed_count=failed_count,
            validation_errors=validation_errors,
            processing_time_ms=processing_time_ms
        )

    def get_buffer(self) -> LogBufferStatus:
        """
        Return buffer metadata for observability.
        """
        stats = self.buffer.stats()
        return LogBufferStatus(
            buffer_size=stats["size"],
            max_size=stats["max_size"],
            oldest_timestamp=stats["oldest_timestamp"],
            newest_timestamp=stats["newest_timestamp"],
            dropped_count=stats["dropped_count"]
        )

    def get_metrics(self) -> IngestionMetrics:
        """
        Return current ingestion metrics.
        """
        return self.metrics 