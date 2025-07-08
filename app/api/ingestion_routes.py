from fastapi import APIRouter, UploadFile, File, Depends, HTTPException, Query, Request, Form
from typing import List, Dict, Any
from app.services.log_ingestion import AdaptiveLogIngestion
from app.services.metrics_service import MetricsService
from app.models.log_models import IngestionRequest, IngestionResponse, IngestionResult
from app.models.metrics_models import MetricsSnapshot
from app.utils.error_utils import log_and_raise
from app.utils.file_utils import read_file
import logging
import asyncio
from app.services.log_normalization import AdaptiveLogParser
import tempfile
import shutil
import os
from app.core.hybrid_detector import HybridDetector
from app.core.workflow import run_detection
from app.core.ML_engine.anomaly_detector import AnomalyDetector
from app.core.ML_engine.feature_extractor import FeatureExtractor
from app.core.rule_engine.rule_engine import RuleEngine
from app.utils.email_utils import send_alert_email
from google.cloud import logging as gcp_logging
import json
from fastapi.responses import JSONResponse, StreamingResponse
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
import re
from agents import Runner
from app.services.log_storage_manager import LogStorageManager
from app.agents.two_agent_workflow import run_two_agent_workflow_stream, run_two_agent_workflow_batch
from app.config.buffer_config import BufferConfig

router = APIRouter()

# Dependency injection (replace with your DI framework or manual instantiation)
buffer_config = BufferConfig()  # This will load from .env or environment

def get_log_ingestion(mode: str = "simulation"):
    return AdaptiveLogIngestion(parser=AdaptiveLogParser(), buffer_config=buffer_config, mode=mode)

metrics_service = MetricsService()
def get_metrics_service():
    return metrics_service

# Global variable to store latest monitoring results
latest_monitoring_results = {
    "anomalies": [],
    "rca_results": []
}

MODEL_DIR = "app/core/ML_engine/models/"
model_cache = {}
feature_list_cache = {}

def normalize_log_type(log_type):
    if not log_type:
        return "unknown"
    log_type = log_type.lower().replace("-", "_").replace(" ", "_")
    log_type = re.sub(r"[^a-z0-9_]+", "", log_type)
    return log_type

def get_log_type(log):
    resource = log.get("raw_log", {}).get("resource", {}) or log.get("resource", {})
    resource_type = resource.get("type") or log.get("resource_type")
    finding = log.get("raw_log", {}).get("finding", {}) or log.get("finding", {})
    if finding:
        return "security_command_center"
    return normalize_log_type(resource_type) if resource_type else "unknown"

def get_detector_for_log_type(log_type):
    norm_type = normalize_log_type(log_type)
    model_path = os.path.join(MODEL_DIR, f"model_{norm_type}.pkl")
    features_path = os.path.join(MODEL_DIR, f"model_{norm_type}.features.json")
    if not os.path.exists(model_path):
        # fallback to generic model if available
        model_path = os.path.join(MODEL_DIR, "model_unknown.pkl")
        features_path = os.path.join(MODEL_DIR, "model_unknown.features.json")
        if not os.path.exists(model_path):
            raise FileNotFoundError(f"No model found for log type {log_type} and no generic fallback.")
    if model_path not in model_cache:
        model_cache[model_path] = AnomalyDetector(model_path=model_path)
    if features_path not in feature_list_cache:
        with open(features_path, "r") as f:
            feature_list_cache[features_path] = json.load(f)
    return model_cache[model_path], feature_list_cache[features_path]

@router.post("/logs/ingest/file", response_model=IngestionResponse)
async def ingest_logs_file(
    file: UploadFile = File(...),
    mode: str = Form("simulation"),
):
    logging.info(f"Received file upload for ingestion. Mode: {mode}")
    tmp_path = None
    log_ingestion = get_log_ingestion(mode)
    try:
        # Flush Redis DB for simulation mode before ingesting
        if mode == "simulation":
            await log_ingestion.log_storage.flush_db()
        # Save the uploaded file to a temp file
        with tempfile.NamedTemporaryFile(delete=False, suffix='.json') as tmp:
            shutil.copyfileobj(file.file, tmp)
            tmp_path = tmp.name
        result = await log_ingestion.ingest_from_file(file_path=tmp_path, source="file_upload", original_format="auto", mode=mode)
        return IngestionResponse(result=result)
    except Exception as e:
        logging.error(f"File ingestion failed: {e}")
        log_and_raise("File ingestion failed", e)
    finally:
        file.file.close()
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass

@router.post("/logs/ingest/stream", response_model=IngestionResponse)
async def ingest_logs_stream(
    request: IngestionRequest,
    log_ingestion: AdaptiveLogIngestion = Depends(get_log_ingestion)
):
    try:
        result = await log_ingestion.ingest_stream(request.logs, source=request.source, original_format="auto")
        return IngestionResponse(result=result)
    except Exception as e:
        log_and_raise("Stream ingestion failed", e)

@router.post("/logs/ingest/gcp")
async def ingest_logs_gcp(
    project_id: str = Form(...),
    service_account_file: UploadFile = File(...),
    mode: str = Form("live"),
    log_ingestion: AdaptiveLogIngestion = Depends(get_log_ingestion)
):
    # Read service account JSON
    sa_json = await service_account_file.read()
    sa_info = json.loads(sa_json)
    # Create GCP logging client
    client = gcp_logging.Client(project=project_id, credentials=gcp_logging.Client.from_service_account_info(sa_info)._credentials)
    # Fetch latest 1000 logs
    entries = client.list_entries(order_by=gcp_logging.DESCENDING, page_size=1000)
    logs = []
    for entry in entries:
        logs.append(entry.to_api_repr())
        if len(logs) >= 1000:
            break
    # No buffer clearing needed; use Redis-based storage
    await log_ingestion.ingest_stream(logs, source="gcp_api", original_format="gcp_json", mode=mode)
    return {"ingested": len(logs)}

# Remove buffer-related endpoints
# --- REMOVED: /logs/buffer, /logs/buffer/full, /logs/buffer/normalized-sample, buffer clearing in ingestion, buffer usage in monitoring ---

# Add Redis-based log/anomaly endpoints
# Update endpoints to use the correct log storage per mode
@router.get("/logs/redis/recent")
async def get_recent_logs(count: int = 100, mode: str = Query("simulation")):
    """Get the most recent logs from Redis."""
    redis_log_storage = get_log_ingestion(mode).log_storage
    max_index = await redis_log_storage.get_current_max_index()
    start = max(1, max_index - count + 1)
    logs = await redis_log_storage.get_logs_range(start, max_index)
    return {"count": len(logs), "logs": logs}

@router.get("/logs/redis/anomalies")
async def get_recent_anomalies(count: int = 100, mode: str = Query("simulation")):
    """Get the most recent anomalies from Redis."""
    redis_log_storage = get_log_ingestion(mode).log_storage
    indices = await redis_log_storage.get_recent_anomalies(count)
    logs = await redis_log_storage.get_logs_range(min(indices, default=1), max(indices, default=0)) if indices else []
    # Filter only is_anomaly logs (defensive)
    logs = [log for log in logs if log.get("is_anomaly")]
    return {"count": len(logs), "anomalies": logs}

@router.get("/logs/redis/range")
async def get_logs_by_index_range(start: int, end: int, mode: str = Query("simulation")):
    """Get logs by log_index range from Redis."""
    redis_log_storage = get_log_ingestion(mode).log_storage
    logs = await redis_log_storage.get_logs_range(start, end)
    return {"count": len(logs), "logs": logs}

@router.get("/logs/redis/anomalies/range")
async def get_anomalies_by_index_range(start: int, end: int, mode: str = Query("simulation")):
    """Get anomalies by log_index range from Redis."""
    redis_log_storage = get_log_ingestion(mode).log_storage
    indices = await redis_log_storage.get_anomaly_indices(start, end)
    logs = await redis_log_storage.get_logs_range(start, end)
    logs = [log for log in logs if log.get("log_index") in indices and log.get("is_anomaly")]
    return {"count": len(logs), "anomalies": logs}

@router.get("/monitor/start")
async def start_monitoring(request: Request):
    lookback = int(request.query_params.get("lookback", 1000))
    api_key = request.query_params.get("api_key")
    email = request.query_params.get("email")
    print(f"[MONITOR] Received email for alerts: {email}")
    log_ingestion = get_log_ingestion()
    log_storage = log_ingestion.log_storage

    async def report_stream():
        group_count = 0
        rca_results = []
        async for report in run_two_agent_workflow_stream(log_storage, lookback=lookback, api_key=api_key):
            group_count += 1
            rca_results.append(report)
            yield f"data: {json.dumps(report, default=str)}\n\n"
        # Update the global variable with the latest RCA results
        global latest_monitoring_results
        latest_monitoring_results["rca_results"] = rca_results
        yield f"data: {json.dumps({'done': True, 'total_alerts': group_count})}\n\n"

    return StreamingResponse(report_stream(), media_type="text/event-stream")

@router.post("/alerts/send-test")
async def send_test_alert_email(request: Request):
    data = await request.json()
    email = data.get("email")
    rca_results = data.get("rca_results")
    print(f"[ALERT-TEST] Received request to send test alert email to: {email}")
    global latest_monitoring_results
    anomalies = latest_monitoring_results.get("anomalies", [])
    if not rca_results:
        rca_results = latest_monitoring_results.get("rca_results", [])
    if not anomalies:
        # fallback to dummy data
        anomalies = [{
            "log": {"severity": "ERROR", "message": "Test anomaly log message"},
            "detection": {"reason": "Test anomaly detected by rule engine"},
            "rca": {"root_cause": "Test root cause", "impact": "Test impact", "remediation": "Test remediation"}
        }]
    if not rca_results:
        rca_results = [{"root_cause": "Test root cause", "impact": "Test impact", "remediation": "Test remediation"}]
    try:
        send_alert_email(email, anomalies, rca_results)
        print(f"[ALERT-TEST] Test alert email sent successfully to {email}.")
        return {"success": True, "message": f"Test alert email sent to {email}"}
    except Exception as e:
        print(f"[ALERT-TEST] Error sending test alert email: {e}")
        return {"success": False, "message": str(e)}, 500

@router.get("/logs/metrics", response_model=MetricsSnapshot)
def get_metrics(
    metrics_service: MetricsService = Depends(get_metrics_service)
):
    return metrics_service.get_snapshot()

@router.post("/gcp/validate-credentials")
async def validate_gcp_credentials(service_account_file: UploadFile = File(...)):
    try:
        sa_json = await service_account_file.read()
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json))
        # Try to list projects to validate credentials
        service = build('cloudresourcemanager', 'v1', credentials=creds)
        _ = service.projects().list(pageSize=1).execute()
        return {"success": True, "message": "Credentials are valid."}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "message": f"Invalid credentials: {e}"})

@router.post("/gcp/projects")
async def list_gcp_projects(service_account_file: UploadFile = File(...)):
    try:
        sa_json = await service_account_file.read()
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json))
        service = build('cloudresourcemanager', 'v1', credentials=creds)
        projects = []
        request = service.projects().list(pageSize=100)
        while request is not None:
            response = request.execute()
            for proj in response.get('projects', []):
                if proj.get('lifecycleState') == 'ACTIVE':
                    projects.append({
                        'projectId': proj['projectId'],
                        'name': proj.get('name', proj['projectId'])
                    })
            request = service.projects().list_next(previous_request=request, previous_response=response)
        return {"success": True, "projects": projects}
    except Exception as e:
        return JSONResponse(status_code=400, content={"success": False, "message": f"Failed to list projects: {e}"})

@router.post("/gcp/log-metadata")
async def get_gcp_log_metadata(service_account_file: UploadFile = File(...), project_id: str = Form(...)):
    try:
        sa_json = await service_account_file.read()
        creds = service_account.Credentials.from_service_account_info(json.loads(sa_json))
        logging_service = build('logging', 'v2', credentials=creds)
        # Get resource types
        resource_types = set()
        severities = set()
        entries = logging_service.entries().list(body={
            "resourceNames": [f"projects/{project_id}"],
            "pageSize": 100
        }).execute()
        for entry in entries.get('entries', []):
            resource = entry.get('resource', {})
            if 'type' in resource:
                resource_types.add(resource['type'])
            severity = entry.get('severity')
            if severity:
                severities.add(severity)
        if not resource_types and not severities:
            return JSONResponse(status_code=400, content={
                "success": False,
                "message": "No log metadata found for this project. Make sure logs exist and your service account has logging.viewer permissions."
            })
        return {"success": True, "resource_types": sorted(resource_types), "severities": sorted(severities)}
    except Exception as e:
        msg = str(e)
        if 'PERMISSION_DENIED' in msg or '403' in msg:
            msg = "Permission denied. Make sure your service account has logging.viewer permissions on this project."
        elif 'SERVICE_DISABLED' in msg:
            msg = "Cloud Logging API is not enabled for this project. Enable it in the Google Cloud Console."
        elif 'not found' in msg or '404' in msg:
            msg = "Project not found or you do not have access."
        elif 'The service is currently unavailable' in msg or '503' in msg:
            msg = "Google Cloud Logging API is temporarily unavailable. Please try again later."
        else:
            msg = f"Failed to get log metadata: {msg}"
        return JSONResponse(status_code=400, content={"success": False, "message": msg}) 