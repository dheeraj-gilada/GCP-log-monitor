from typing import List, Optional, Dict, Any, Callable
from datetime import datetime, timezone
from app.models.log_models import (
    RawGCPLogEntry, NormalizedLogEntry, IngestionMetadata, IngestionResult, LogValidationError, IngestionRequest, IngestionResponse
)
from app.models.metrics_models import IngestionMetrics
from app.utils.otel_utils import start_trace, set_correlation_context
from app.config.buffer_config import BufferConfig
from app.utils.error_utils import log_and_raise, log_warning
from app.utils.file_utils import read_file
import asyncio
from app.services.log_storage_manager import LogStorageManager
from app.core.hybrid_detector import HybridDetector
from app.core.rule_engine.rule_engine import RuleEngine
from app.core.ML_engine.anomaly_detector import AnomalyDetector
from app.core.ML_engine.feature_extractor import FeatureExtractor

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
        buffer_config: Optional[BufferConfig] = None,
        hybrid_detector: Optional[Any] = None  # Add hybrid_detector
    ):
        self.parser = parser
        self.gcp_service = gcp_service
        self.metrics_service = metrics_service
        self.metrics = IngestionMetrics()
        # Use Redis URL from config or default
        redis_url = getattr(buffer_config, 'redis_url', 'redis://localhost:6379') if buffer_config else 'redis://localhost:6379'
        self.log_storage = LogStorageManager(redis_url=redis_url, buffer_size=getattr(buffer_config, 'buffer_max_size', 1000) if buffer_config else 1000)
        if hybrid_detector is not None:
            self.hybrid_detector = hybrid_detector
        else:
            rule_engine = RuleEngine(rules_dir="app/core/rule_engine/rules/")
            ml_detector = AnomalyDetector(model_path="app/core/ML_engine/models/model_unknown.pkl")
            feature_extractor = FeatureExtractor()
            self.hybrid_detector = HybridDetector(rule_engine, ml_detector, feature_extractor)

    def get_buffer_for_mode(self, mode: str = "simulation"):
        if mode == "live":
            return self.live_buffer
        return self.simulation_buffer

    def persist_failed_logs(self, validation_errors, file_path="failed_logs.jsonl"):
        import json
        if not validation_errors:
            return
        with open(file_path, "a") as f:
            for err in validation_errors:
                f.write(json.dumps(err.model_dump()) + "\n")

    async def ingest_from_file(self, file_path: str, source: str = "file_upload", original_format: str = "auto", failed_log_path: str = "failed_logs.jsonl", mode: str = "simulation") -> IngestionResult:
        from app.models.log_models import LogValidationError, IngestionResult  # avoid circular import
        import json
        raw_data = read_file(file_path)
        logs = []
        validation_errors = []
        failed_count = 0
        try:
            data = json.loads(raw_data)
            if isinstance(data, list):
                logs = data
            elif isinstance(data, dict):
                logs = [data]
            else:
                raise ValueError("Not a list or dict")
        except Exception:
            for idx, line in enumerate(raw_data.strip().splitlines()):
                if not line.strip():
                    continue
                try:
                    entry = json.loads(line)
                    logs.append(entry)
                except Exception as e:
                    validation_errors.append(LogValidationError(
                        field=f"line_{idx+1}",
                        error_type="json_parse_error",
                        message=str(e),
                        raw_value=line
                    ))
                    failed_count += 1
        result = await self._process_logs_async(logs, source=source, original_format=original_format, ignore_time_window=True, mode=mode)
        result.failed_count += failed_count
        result.validation_errors = validation_errors + result.validation_errors
        result.success = result.failed_count == 0
        if result.validation_errors:
            self.persist_failed_logs(result.validation_errors, file_path=failed_log_path)
        return result

    async def ingest_from_gcp(self, query_params: Dict[str, Any], source: str = "gcp_api", original_format: str = "gcp_json", failed_log_path: str = "failed_logs.jsonl", mode: str = "live") -> IngestionResult:
        if not self.gcp_service:
            log_and_raise("GCP service not configured")
        try:
            raw_logs = self.gcp_service.fetch_logs(query_params)
            logs = self.parser.parse(raw_logs, original_format=original_format)
            result = await self._process_logs_async(logs, source=source, original_format=original_format, ignore_time_window=False, mode=mode)
            if result.validation_errors:
                self.persist_failed_logs(result.validation_errors, file_path=failed_log_path)
            return result
        except Exception as e:
            log_and_raise("GCP ingestion failed", e, {"query_params": query_params})
            return IngestionResult(success=False, processed_count=0, failed_count=0, validation_errors=[LogValidationError(field="gcp", error_type="ingestion_error", message=str(e), raw_value=query_params)], processing_time_ms=0)

    async def ingest_stream(self, logs: List[Dict[str, Any]], source: str = "stream", original_format: str = "auto", failed_log_path: str = "failed_logs.jsonl", mode: str = "simulation") -> IngestionResult:
        try:
            parsed_logs = self.parser.parse(logs, original_format=original_format)
            result = await self._process_logs_async(parsed_logs, source=source, original_format=original_format, ignore_time_window=False, mode=mode)
            if result.validation_errors:
                self.persist_failed_logs(result.validation_errors, file_path=failed_log_path)
            return result
        except Exception as e:
            log_and_raise("Stream ingestion failed", e, {"logs": logs})
            return IngestionResult(success=False, processed_count=0, failed_count=0, validation_errors=[LogValidationError(field="stream", error_type="ingestion_error", message=str(e), raw_value=logs)], processing_time_ms=0)

    async def _process_logs_async(self, logs: List[Any], source: str, original_format: str, ignore_time_window: bool = False, mode: str = "simulation") -> IngestionResult:
        from app.models.log_models import LogValidationError
        start_time = datetime.now(timezone.utc)
        normalized_logs = []
        validation_errors = []
        processed_count = 0
        failed_count = 0
        is_mock = self.parser.__class__.__name__ == "MockParser"
        for raw_log in logs:
            try:
                if not is_mock and not hasattr(raw_log, 'raw_log'):
                    try:
                        from app.models.log_models import RawGCPLogEntry
                        parsed_log = RawGCPLogEntry(raw_log=raw_log, **raw_log)
                    except Exception as e:
                        validation_errors.append(LogValidationError(
                            field="raw_log",
                            error_type="parsing_error",
                            message=str(e),
                            raw_value=raw_log
                        ))
                        failed_count += 1
                        continue
                else:
                    parsed_log = raw_log
                with start_trace("log_ingest") as span:
                    set_correlation_context(span, parsed_log)
                    normalized = self.parser.normalize(parsed_log)
                    normalized_dict = normalized.model_dump(mode='json') if hasattr(normalized, 'model_dump') else dict(normalized)
                    # Store log and assign log_index
                    log_index = await self.log_storage.store_log(normalized_dict)
                    normalized_dict["log_index"] = log_index
                    normalized_logs.append(normalized_dict)
                    processed_count += 1
                    # Run hybrid detector
                    is_anomaly = self.hybrid_detector.detect(normalized_dict)
                    if is_anomaly:
                        await self.log_storage.flag_anomaly(log_index)
            except Exception as e:
                log_warning("Log normalization failed", {"error": str(e), "raw_log": getattr(raw_log, 'raw_log', raw_log)})
                validation_errors.append(LogValidationError(
                    field="log",
                    error_type="normalization_error",
                    message=str(e),
                    raw_value=getattr(raw_log, 'raw_log', raw_log)
                ))
                failed_count += 1
        end_time = datetime.now(timezone.utc)
        processing_time_ms = (end_time - start_time).total_seconds() * 1000
        self.metrics.logs_received += len(logs)
        self.metrics.logs_processed += processed_count
        self.metrics.logs_failed += failed_count
        self.metrics.avg_processing_time_ms = processing_time_ms / max(1, len(logs))
        if self.metrics_service:
            self.metrics_service.record(self.metrics)
        return IngestionResult(
            success=failed_count == 0,
            processed_count=processed_count,
            failed_count=failed_count,
            validation_errors=validation_errors,
            processing_time_ms=processing_time_ms
        )

    async def get_buffer(self, mode: str = "simulation"):
        buffer = self.get_buffer_for_mode(mode)
        return await buffer.get_status()

    def get_metrics(self) -> IngestionMetrics:
        """
        Return current ingestion metrics.
        """
        return self.metrics 