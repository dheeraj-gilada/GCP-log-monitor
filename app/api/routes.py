"""
Main API routes for GCP Log Monitoring system.
Handles file uploads, GCP configuration, alerts, and monitoring endpoints.
"""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
import json
import asyncio

from app.api.dependencies import (
    validate_api_access,
    validate_gcp_config,
    validate_openai_config_dep,
    validate_email_config,
    get_pagination_params,
    validate_file_upload,
    get_current_settings
)
from app.models.schemas import (
    FileUploadResponse,
    GCPConfigRequest,
    GCPConfigResponse,
    AlertPreviewRequest,
    AlertSendRequest,
    MonitoringStats,
    SystemHealth
)
from app.config import Settings

# Create router
router = APIRouter(tags=["monitoring"], dependencies=[Depends(validate_api_access)])


@router.get("/health", response_model=SystemHealth)
async def get_system_health():
    """Get system health status and service availability."""
    # TODO: Implement actual health checks in Phase 2
    return SystemHealth(
        status="healthy",
        uptime_seconds=0,  # TODO: Calculate actual uptime
        gcp_connected=False,  # TODO: Check GCP connection
        openai_connected=False,  # TODO: Check OpenAI connection
        email_service_healthy=False,  # TODO: Check email service
        logs_in_buffer=0,
        buffer_utilization=0.0,
        processing_rate_per_second=0.0
    )


@router.get("/stats", response_model=MonitoringStats)
async def get_monitoring_stats(
    pagination: dict = Depends(get_pagination_params)
):
    """Get real-time monitoring statistics."""
    from datetime import datetime, timedelta
    
    # TODO: Implement actual stats calculation in Phase 2.5
    now = datetime.utcnow()
    window_start = now - timedelta(minutes=10)
    
    return MonitoringStats(
        total_logs=0,
        error_rate=0.0,
        avg_latency=None,
        active_anomalies=0,
        alerts_sent=0,
        window_start=window_start,
        window_end=now,
        by_resource_type={},
        by_severity={}
    )


# File Upload Endpoints

@router.post("/upload", response_model=FileUploadResponse)
async def upload_log_file(
    file: UploadFile = File(...),
    log_format: str = Form(default="auto")  # auto, json, text
):
    """Upload and parse log files."""
    # Validate file
    await validate_file_upload(
        file_size=file.size or 0,
        file_type=file.content_type or "text/plain"
    )
    
    try:
        # Read file content
        content = await file.read()
        content_str = content.decode('utf-8')
        
        # Calculate file size in MB
        file_size_mb = len(content) / (1024 * 1024)
        
        # TODO: Implement actual log parsing in Phase 2
        # For now, just return a success response
        logs_processed = content_str.count('\n') if content_str else 0
        
        return FileUploadResponse(
            success=True,
            message=f"File '{file.filename}' uploaded successfully",
            logs_processed=logs_processed,
            file_size_mb=round(file_size_mb, 2)
        )
        
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=400,
            detail="File must be valid UTF-8 encoded text"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to process file: {str(e)}"
        )


@router.get("/logs")
async def get_recent_logs(
    pagination: dict = Depends(get_pagination_params),
    severity: Optional[str] = None,
    resource_type: Optional[str] = None
):
    """Get recent logs with optional filtering."""
    # TODO: Implement actual log retrieval in Phase 2
    return {
        "logs": [],
        "total": 0,
        "skip": pagination["skip"],
        "limit": pagination["limit"]
    }


# GCP Configuration Endpoints

@router.post("/gcp/configure", response_model=GCPConfigResponse)
async def configure_gcp(
    config: GCPConfigRequest,
    settings: Settings = Depends(get_current_settings)
):
    """Configure GCP connection settings."""
    try:
        # TODO: Implement actual GCP configuration in Phase 2
        # For now, validate the request and return success
        
        # Basic validation
        if not config.project_id:
            raise HTTPException(status_code=400, detail="Project ID is required")
        
        if not config.service_account_path:
            raise HTTPException(status_code=400, detail="Service account path is required")
        
        # TODO: Test actual GCP connection
        connection_tested = False
        
        return GCPConfigResponse(
            success=True,
            message="GCP configuration saved successfully",
            project_id=config.project_id,
            connection_tested=connection_tested
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to configure GCP: {str(e)}"
        )


@router.get("/gcp/status")
async def get_gcp_status():
    """Get current GCP connection status."""
    # TODO: Implement actual GCP status check in Phase 2
    return {
        "connected": False,
        "project_id": None,
        "last_connection_test": None,
        "error_message": "GCP service not implemented yet"
    }


@router.post("/gcp/test-connection")
async def test_gcp_connection():
    """Test GCP connection with current configuration."""
    # TODO: Implement actual connection test in Phase 2
    return {
        "success": False,
        "message": "Connection test not implemented yet",
        "details": {}
    }


# Anomaly and Alert Endpoints

@router.get("/anomalies")
async def get_anomalies(
    pagination: dict = Depends(get_pagination_params),
    severity: Optional[str] = None,
    active_only: bool = True
):
    """Get detected anomalies."""
    # TODO: Implement actual anomaly retrieval in Phase 2
    return {
        "anomalies": [],
        "total": 0,
        "skip": pagination["skip"],
        "limit": pagination["limit"]
    }


@router.get("/anomalies/{anomaly_id}")
async def get_anomaly_details(anomaly_id: str):
    """Get detailed information about a specific anomaly."""
    # TODO: Implement in Phase 2
    raise HTTPException(status_code=404, detail="Anomaly not found")


@router.get("/alerts")
async def get_alerts(
    pagination: dict = Depends(get_pagination_params),
    status: Optional[str] = None
):
    """Get generated alerts."""
    # TODO: Implement actual alert retrieval in Phase 3
    return {
        "alerts": [],
        "total": 0,
        "skip": pagination["skip"],
        "limit": pagination["limit"]
    }


@router.post("/alerts/preview")
async def preview_alert(
    request: AlertPreviewRequest,
    _: bool = Depends(validate_openai_config_dep)
):
    """Preview alert content before sending."""
    # TODO: Implement alert preview in Phase 3
    return {
        "success": False,
        "message": "Alert preview not implemented yet",
        "html_content": None,
        "markdown_content": None
    }


@router.post("/alerts/send")
async def send_alert(
    request: AlertSendRequest,
    _: bool = Depends(validate_email_config)
):
    """Send an alert via email."""
    # TODO: Implement alert sending in Phase 4
    return {
        "success": False,
        "message": "Alert sending not implemented yet",
        "delivery_id": None
    }


@router.get("/alerts/{alert_id}")
async def get_alert_details(alert_id: str):
    """Get detailed information about a specific alert."""
    # TODO: Implement in Phase 3
    raise HTTPException(status_code=404, detail="Alert not found")


# Configuration and Settings

@router.get("/config")
async def get_configuration(settings: Settings = Depends(get_current_settings)):
    """Get current system configuration (sanitized)."""
    return {
        "app_name": settings.app_name,
        "app_version": settings.app_version,
        "log_buffer_minutes": settings.log_buffer_minutes,
        "max_buffer_size": settings.max_buffer_size,
        "anomaly_check_interval": settings.anomaly_check_interval,
        "error_rate_threshold": settings.error_rate_threshold,
        "latency_threshold_ms": settings.latency_threshold_ms,
        "repeated_error_threshold": settings.repeated_error_threshold,
        "email_rate_limit_minutes": settings.email_rate_limit_minutes,
        # Don't expose sensitive information
        "openai_configured": bool(settings.openai_api_key),
        "sendgrid_configured": bool(settings.sendgrid_api_key),
        "gcp_configured": bool(settings.gcp_project_id and settings.gcp_service_account_path)
    }


@router.post("/config/validate")
async def validate_configuration():
    """Validate all system configurations."""
    from app.config import validate_gcp_credentials, validate_openai_config, validate_sendgrid_config
    
    validations = {
        "gcp": validate_gcp_credentials(),
        "openai": validate_openai_config(),
        "sendgrid": validate_sendgrid_config()
    }
    
    all_valid = all(validations.values())
    
    return {
        "valid": all_valid,
        "details": validations,
        "message": "All configurations valid" if all_valid else "Some configurations are invalid"
    }


# Development and Testing Endpoints (only available in debug mode)

@router.get("/debug/trigger-test-anomaly")
async def trigger_test_anomaly(settings: Settings = Depends(get_current_settings)):
    """Trigger a test anomaly for development purposes."""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Endpoint not available in production")
    
    # TODO: Implement test anomaly generation in Phase 2
    return {"message": "Test anomaly triggered", "anomaly_id": "test-123"}


@router.get("/debug/system-info")
async def get_debug_info(settings: Settings = Depends(get_current_settings)):
    """Get detailed system information for debugging."""
    if not settings.debug:
        raise HTTPException(status_code=404, detail="Endpoint not available in production")
    
    import sys
    import os
    
    return {
        "python_version": sys.version,
        "working_directory": os.getcwd(),
        "environment_variables": [k for k in os.environ.keys() if not k.startswith('OPENAI') and not k.startswith('SENDGRID')],
        "settings": settings.dict(exclude={"openai_api_key", "sendgrid_api_key"})
    }
