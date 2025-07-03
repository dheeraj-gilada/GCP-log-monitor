from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query
from typing import List, Dict, Any
from app.services.log_ingestion import AdaptiveLogIngestion
from app.services.metrics_service import MetricsService
from app.models.log_models import IngestionRequest, IngestionResponse, IngestionResult, LogBufferStatus
from app.models.metrics_models import MetricsSnapshot
from app.utils.error_utils import log_and_raise
from app.utils.buffer_utils import LogBuffer
from app.utils.file_utils import read_file
import logging

router = APIRouter()

# Dependency injection (replace with your DI framework or manual instantiation)
adaptive_log_ingestion = AdaptiveLogIngestion(parser=None)  # Inject real parser in app startup
def get_log_ingestion():
    return adaptive_log_ingestion

metrics_service = MetricsService()
def get_metrics_service():
    return metrics_service

@router.post("/logs/ingest/file", response_model=IngestionResponse)
def ingest_logs_file(
    file: UploadFile = File(...),
    log_ingestion: AdaptiveLogIngestion = Depends(get_log_ingestion)
):
    """
    Ingest logs from an uploaded file (JSON or text).
    """
    try:
        content = file.file.read().decode()
        result = log_ingestion.ingest_from_file(file_path=file.filename, source="file_upload", original_format="auto")
        return IngestionResponse(result=result)
    except Exception as e:
        log_and_raise("File ingestion failed", e)

@router.post("/logs/ingest/stream", response_model=IngestionResponse)
def ingest_logs_stream(
    request: IngestionRequest,
    log_ingestion: AdaptiveLogIngestion = Depends(get_log_ingestion)
):
    """
    Ingest logs from a real-time stream (JSON array in request body).
    """
    try:
        result = log_ingestion.ingest_stream(request.logs, source=request.source, original_format="auto")
        return IngestionResponse(result=result)
    except Exception as e:
        log_and_raise("Stream ingestion failed", e)

@router.post("/logs/ingest/gcp", response_model=IngestionResponse)
def ingest_logs_gcp(
    query_params: Dict[str, Any],
    log_ingestion: AdaptiveLogIngestion = Depends(get_log_ingestion)
):
    """
    Ingest logs from GCP Logging API using query parameters.
    """
    try:
        result = log_ingestion.ingest_from_gcp(query_params, source="gcp_api", original_format="gcp_json")
        return IngestionResponse(result=result)
    except Exception as e:
        log_and_raise("GCP ingestion failed", e)

@router.get("/logs/buffer")
def get_log_buffer(
    log_ingestion: AdaptiveLogIngestion = Depends(get_log_ingestion)
):
    """
    Get log buffer metadata for observability.
    """
    return log_ingestion.get_buffer()

@router.get("/logs/metrics", response_model=MetricsSnapshot)
def get_metrics(
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    """
    Get current ingestion and processing metrics snapshot.
    """
    return metrics_service.get_snapshot() 