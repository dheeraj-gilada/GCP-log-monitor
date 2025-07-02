"""
API routes for the GCP log monitoring system.
Integrates with all core services for comprehensive monitoring.
"""

from fastapi import APIRouter, HTTPException, UploadFile, File, BackgroundTasks, Depends
from fastapi.responses import JSONResponse, HTMLResponse
from typing import List, Dict, Any, Optional
from datetime import datetime
import json
import logging

from app.api.dependencies import get_monitoring_engine
from app.core.monitoring_engine import MonitoringEngine
from app.models.schemas import LogEntry, Anomaly, Alert

router = APIRouter()

# ==========================================
# MONITORING ENGINE ENDPOINTS
# ==========================================

@router.post("/monitoring/start")
async def start_monitoring(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Start the monitoring engine."""
    try:
        if engine.is_running():
            return {"success": False, "message": "Monitoring already running"}
        
        await engine.start()
        return {
            "success": True,
            "message": "Monitoring engine started successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to start monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/stop")
async def stop_monitoring(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Stop the monitoring engine."""
    try:
        if not engine.is_running():
            return {"success": False, "message": "Monitoring not running"}
        
        await engine.stop()
        return {
            "success": True,
            "message": "Monitoring engine stopped successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to stop monitoring: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/monitoring/status")
async def get_monitoring_status(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Get current monitoring status and statistics."""
    try:
        stats = await engine.get_monitoring_stats()
        return {
            "success": True,
            "status": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to get monitoring status: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/force-analysis")
async def force_analysis(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Force immediate analysis cycle (for testing/debugging)."""
    try:
        result = await engine.force_analysis()
        return {
            "success": True,
            "analysis_result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to force analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/monitoring/configure")
async def configure_monitoring(
    config: Dict[str, Any],
    engine: MonitoringEngine = Depends(get_monitoring_engine)
):
    """Update monitoring configuration."""
    try:
        await engine.configure_monitoring(**config)
        return {
            "success": True,
            "message": "Configuration updated successfully",
            "updated_config": config,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to update configuration: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# LOG INGESTION ENDPOINTS
# ==========================================

@router.post("/logs/upload")
async def upload_logs(
    file: UploadFile = File(...),
    log_format: str = "auto",
    engine: MonitoringEngine = Depends(get_monitoring_engine)
):
    """Upload and ingest log file."""
    try:
        # Validate file type
        if not file.filename.endswith(('.txt', '.log', '.json')):
            raise HTTPException(
                status_code=400, 
                detail="Only .txt, .log, and .json files are supported"
            )
        
        # Read file content
        content = await file.read()
        file_content = content.decode('utf-8')
        
        # Ingest logs
        result = await engine.ingest_file(file_content, file.filename, log_format)
        
        return {
            "success": True,
            "ingestion_result": result,
            "filename": file.filename,
            "file_size_kb": len(content) / 1024,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except UnicodeDecodeError:
        raise HTTPException(status_code=400, detail="File encoding not supported. Please use UTF-8.")
    except Exception as e:
        logging.error(f"Failed to upload logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/recent")
async def get_recent_logs(
    limit: int = 100,
    severity: Optional[str] = None,
    resource_type: Optional[str] = None,
    engine: MonitoringEngine = Depends(get_monitoring_engine)
):
    """Get recent logs with optional filtering."""
    try:
        # Get logs from engine
        logs = await engine.get_recent_logs(limit)
        
        # Apply additional filters if specified
        if severity:
            logs = [log for log in logs if log.get('severity') == severity.upper()]
        
        if resource_type:
            logs = [log for log in logs if log.get('resource', {}).get('type') == resource_type]
        
        return {
            "success": True,
            "logs": logs,
            "count": len(logs),
            "filters": {
                "limit": limit,
                "severity": severity,
                "resource_type": resource_type
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Failed to get recent logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/logs/buffer-stats")
async def get_buffer_stats(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Get log buffer statistics."""
    try:
        stats = await engine.log_service.get_buffer_stats()
        return {
            "success": True,
            "buffer_stats": stats,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to get buffer stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# GCP INTEGRATION ENDPOINTS
# ==========================================

@router.get("/gcp/test-connection")
async def test_gcp_connection(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Test GCP connection."""
    try:
        result = await engine.gcp_service.test_connection()
        return {
            "success": True,
            "connection_test": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"GCP connection test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gcp/resources")
async def get_gcp_resources(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Get available GCP resources."""
    try:
        resources = await engine.gcp_service.get_available_resources()
        return {
            "success": True,
            "resources": resources,
            "count": len(resources),
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to get GCP resources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/gcp/metrics")
async def get_gcp_metrics(
    hours: int = 1,
    engine: MonitoringEngine = Depends(get_monitoring_engine)
):
    """Get GCP log metrics for specified time period."""
    try:
        metrics = await engine.gcp_service.get_log_metrics(hours=hours)
        return {
            "success": True,
            "metrics": metrics,
            "time_period_hours": hours,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to get GCP metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/gcp/fetch-logs")
async def fetch_gcp_logs(
    request: Dict[str, Any],
    engine: MonitoringEngine = Depends(get_monitoring_engine)
):
    """Fetch logs from GCP with specific filters."""
    try:
        # Parse request parameters
        hours = request.get('hours', 1)
        max_entries = request.get('max_entries', 500)
        severity_filter = request.get('severity_filter')
        
        # Fetch logs
        logs = await engine.gcp_service.fetch_recent_logs(
            minutes=hours * 60,
            max_entries=max_entries
        )
        
        # Convert to dict format
        log_dicts = [log.dict() for log in logs]
        
        return {
            "success": True,
            "logs": log_dicts,
            "count": len(log_dicts),
            "parameters": request,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Failed to fetch GCP logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# ANOMALY DETECTION ENDPOINTS  
# ==========================================

@router.post("/anomalies/analyze")
async def analyze_current_logs(
    use_ai_analysis: bool = True,
    engine: MonitoringEngine = Depends(get_monitoring_engine)
):
    """Analyze current logs for anomalies."""
    try:
        # Get recent logs
        logs = await engine.log_service.get_logs_in_window()
        
        if not logs:
            return {
                "success": True,
                "anomalies": [],
                "message": "No logs available for analysis",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Analyze for anomalies
        anomalies = await engine.anomaly_service.analyze_logs(logs, use_ai_analysis)
        
        # Convert to dict format
        anomaly_dicts = [anomaly.dict() for anomaly in anomalies]
        
        return {
            "success": True,
            "anomalies": anomaly_dicts,
            "logs_analyzed": len(logs),
            "anomalies_detected": len(anomalies),
            "ai_analysis_used": use_ai_analysis,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Failed to analyze logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/anomalies/configure-thresholds")
async def configure_anomaly_thresholds(
    thresholds: Dict[str, float],
    engine: MonitoringEngine = Depends(get_monitoring_engine)
):
    """Configure anomaly detection thresholds."""
    try:
        engine.anomaly_service.configure_thresholds(**thresholds)
        
        return {
            "success": True,
            "message": "Thresholds updated successfully",
            "updated_thresholds": thresholds,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Failed to configure thresholds: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# SERVICE TESTING ENDPOINTS
# ==========================================

@router.get("/services/test-all")
async def test_all_services(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Test all service connections and configurations."""
    try:
        results = await engine.test_services()
        
        # Add overall health assessment
        all_healthy = all(
            result.get('connected', result.get('configured', result.get('available', False)))
            for result in results.values()
        )
        
        return {
            "success": True,
            "overall_health": "healthy" if all_healthy else "degraded",
            "service_tests": results,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Service tests failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/services/gpt/test")
async def test_gpt_service(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Test GPT service with a simple analysis."""
    try:
        if not engine.anomaly_service.gpt_service.is_available():
            return {
                "success": False,
                "message": "GPT service not available - check OpenAI API key configuration",
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Create a test log entry
        from app.models.schemas import LogEntry, LogSeverity, LogResource, ResourceType
        
        test_log = LogEntry(
            timestamp=datetime.utcnow(),
            severity=LogSeverity.ERROR,
            message="Database connection timeout - unable to connect to primary database",
            resource=LogResource(type=ResourceType.CLOUD_SQL, labels={"instance": "test"}),
            source="test"
        )
        
        # Test single log analysis
        analysis = await engine.anomaly_service.gpt_service.analyze_single_log_entry(test_log)
        
        return {
            "success": True,
            "message": "GPT service is working",
            "test_analysis": analysis,
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"GPT service test failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# ALERT ENDPOINTS
# ==========================================

@router.get("/alerts/recent")
async def get_recent_alerts(limit: int = 50):
    """Get recent alerts (placeholder - would integrate with alert storage)."""
    try:
        # This would integrate with an alert storage system
        # For now, return empty list
        return {
            "success": True,
            "alerts": [],
            "count": 0,
            "message": "Alert storage integration pending",
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logging.error(f"Failed to get recent alerts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/alerts/test-email")
async def test_email_alert(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Send a test email alert."""
    try:
        # Test email service
        email_test = await engine.email_service.test_connection()
        
        if not email_test.get('configured', False):
            return {
                "success": False,
                "message": "Email service not configured properly",
                "details": email_test,
                "timestamp": datetime.utcnow().isoformat()
            }
        
        # Send test email
        test_context = {
            "alert": {
                "title": "Test Alert",
                "description": "This is a test alert to verify email configuration",
                "severity": "HIGH",
                "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
            },
            "monitoring_url": "http://localhost:8000/monitoring",
            "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        }
        
        await engine.email_service.send_test_alert(test_context)
        
        return {
            "success": True,
            "message": "Test email sent successfully",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Failed to send test email: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==========================================
# UTILITY ENDPOINTS
# ==========================================

@router.get("/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "service": "GCP Log Monitoring System",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "2.0.0"
    }


@router.get("/info")
async def get_system_info(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Get system information and capabilities."""
    try:
        stats = await engine.get_monitoring_stats()
        
        return {
            "success": True,
            "system_info": {
                "service_name": "GCP Log Monitoring System",
                "version": "2.0.0",
                "capabilities": [
                    "File log ingestion",
                    "GCP Cloud Logging integration", 
                    "Real-time log streaming",
                    "Hybrid anomaly detection",
                    "AI-powered analysis",
                    "Email alerting",
                    "WebSocket real-time updates"
                ],
                "monitoring_stats": stats
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        logging.error(f"Failed to get system info: {e}")
        raise HTTPException(status_code=500, detail=str(e))
