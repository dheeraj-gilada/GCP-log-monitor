"""
Dependency injection for FastAPI routes.
Provides access to core services and validation functions.
"""

from fastapi import Depends, HTTPException, status
from functools import lru_cache
import logging

from app.config import get_settings, Settings
from app.config import validate_gcp_credentials, validate_openai_config, validate_sendgrid_config
from app.core.monitoring_engine import MonitoringEngine

# Global monitoring engine instance
_monitoring_engine = None


def get_monitoring_engine() -> MonitoringEngine:
    """Get or create monitoring engine instance."""
    global _monitoring_engine
    
    if _monitoring_engine is None:
        _monitoring_engine = MonitoringEngine()
        logging.info("Monitoring engine instance created")
    
    return _monitoring_engine


def validate_api_access():
    """Basic API access validation."""
    # Could add API key validation, rate limiting, etc.
    pass


@lru_cache()
def get_current_settings():
    """Get current settings (cached)."""
    return get_settings()


def validate_file_upload(file_size: int, file_type: str):
    """Validate uploaded file parameters."""
    max_size = 50 * 1024 * 1024  # 50MB
    
    if file_size > max_size:
        raise HTTPException(
            status_code=413,
            detail=f"File too large. Maximum size is {max_size // (1024 * 1024)}MB"
        )
    
    allowed_types = ["text/plain", "application/json", "text/x-log"]
    
    if file_type not in allowed_types and not file_type.startswith("text/"):
        raise HTTPException(
            status_code=400,
            detail="Unsupported file type. Please upload text or JSON files."
        )


def get_pagination_params(skip: int = 0, limit: int = 100):
    """Get pagination parameters with validation."""
    if skip < 0:
        raise HTTPException(
            status_code=400,
            detail="Skip parameter must be non-negative"
        )
    
    if limit <= 0 or limit > 1000:
        raise HTTPException(
            status_code=400,
            detail="Limit must be between 1 and 1000"
        )
    
    return {"skip": skip, "limit": limit}


def validate_monitoring_config(config: dict):
    """Validate monitoring configuration parameters."""
    allowed_keys = {
        'analysis_interval_seconds',
        'window_minutes',
        'enable_gcp_streaming',
        'enable_email_alerts',
        'enable_ai_analysis',
        'min_logs_for_analysis',
        'alert_cooldown_minutes',
        'error_rate_threshold',
        'latency_threshold_ms',
        'volume_spike_multiplier'
    }
    
    for key in config.keys():
        if key not in allowed_keys:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid configuration key: {key}"
            )
    
    # Validate specific parameters
    if 'analysis_interval_seconds' in config:
        value = config['analysis_interval_seconds']
        if not isinstance(value, int) or value < 10 or value > 3600:
            raise HTTPException(
                status_code=400,
                detail="analysis_interval_seconds must be between 10 and 3600"
            )
    
    if 'window_minutes' in config:
        value = config['window_minutes']
        if not isinstance(value, int) or value < 1 or value > 60:
            raise HTTPException(
                status_code=400,
                detail="window_minutes must be between 1 and 60"
            )
    
    if 'error_rate_threshold' in config:
        value = config['error_rate_threshold']
        if not isinstance(value, (int, float)) or value < 0 or value > 1:
            raise HTTPException(
                status_code=400,
                detail="error_rate_threshold must be between 0 and 1"
            )


def require_monitoring_running(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Require monitoring engine to be running."""
    if not engine.is_running():
        raise HTTPException(
            status_code=400,
            detail="Monitoring engine is not running. Start monitoring first."
        )
    return engine


def require_gcp_connected(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Require GCP service to be connected."""
    if not engine.gcp_service.is_connected():
        raise HTTPException(
            status_code=400,
            detail="GCP service not connected. Check configuration and credentials."
        )
    return engine


def require_email_configured(engine: MonitoringEngine = Depends(get_monitoring_engine)):
    """Require email service to be configured."""
    if not engine.email_service.is_configured():
        raise HTTPException(
            status_code=400,
            detail="Email service not configured. Check SendGrid configuration."
        )
    return engine


async def validate_gcp_config(settings: Settings = Depends(get_current_settings)):
    """Validate GCP configuration is available."""
    if not validate_gcp_credentials():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="GCP credentials not configured or invalid"
        )
    return True


async def validate_openai_config_dep(settings: Settings = Depends(get_current_settings)):
    """Validate OpenAI configuration is available."""
    if not validate_openai_config():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="OpenAI API key not configured or invalid"
        )
    return True


async def validate_email_config(settings: Settings = Depends(get_current_settings)):
    """Validate email service configuration."""
    if not validate_sendgrid_config():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Email service not configured"
        )
    return True


# Service dependencies (will be implemented in later phases)
# These will return actual service instances

def get_log_ingestion_service():
    """Get log ingestion service."""
    # TODO: Implement in Phase 2
    from app.services.log_ingestion import LogIngestionService
    return LogIngestionService()


def get_gcp_service():
    """Get GCP service instance."""
    # TODO: Implement in Phase 2
    from app.services.gcp_service import GCPService
    return GCPService()


def get_email_service():
    """Get email service instance."""
    # TODO: Implement in Phase 4
    from app.services.email_service import EmailService
    return EmailService()


def get_anomaly_detection_service():
    """Get anomaly detection service."""
    # TODO: Implement in Phase 2
    from app.services.anomaly_detection import AnomalyDetectionService
    return AnomalyDetectionService()


def get_gpt_reasoning_service():
    """Get GPT reasoning service."""
    # TODO: Implement in Phase 3
    from app.services.gpt_reasoning import GPTReasoningService
    return GPTReasoningService()
