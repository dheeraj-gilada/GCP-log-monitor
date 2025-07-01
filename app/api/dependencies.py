"""
Shared dependencies for API endpoints.
Includes validation, authentication, and service injection.
"""

from fastapi import Depends, HTTPException, status
from typing import Optional

from app.config import get_settings, Settings
from app.config import validate_gcp_credentials, validate_openai_config, validate_sendgrid_config


def get_current_settings() -> Settings:
    """Get application settings."""
    return get_settings()


async def validate_api_access():
    """
    Placeholder for API authentication/authorization.
    TODO: Implement authentication middleware when needed.
    
    For now, this is a pass-through that could be extended with:
    - API key validation
    - JWT token verification  
    - Rate limiting
    - IP allowlisting
    """
    # In production, add authentication logic here
    # Example:
    # if not validate_api_key(request.headers.get("X-API-Key")):
    #     raise HTTPException(status_code=401, detail="Invalid API key")
    pass


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

def get_monitoring_engine():
    """Get monitoring engine instance."""
    # TODO: Implement in Phase 2.5
    from app.core.monitoring_engine import MonitoringEngine
    return MonitoringEngine()


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


# Utility dependencies

async def get_pagination_params(
    skip: int = 0, 
    limit: int = 100
) -> dict:
    """Get pagination parameters with validation."""
    if skip < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Skip parameter must be >= 0"
        )
    
    if limit < 1 or limit > 1000:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Limit must be between 1 and 1000"
        )
    
    return {"skip": skip, "limit": limit}


async def validate_file_upload(
    file_size: int,
    file_type: str,
    max_size_mb: int = 50
) -> bool:
    """Validate uploaded file constraints."""
    max_size_bytes = max_size_mb * 1024 * 1024
    
    if file_size > max_size_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File size exceeds {max_size_mb}MB limit"
        )
    
    allowed_types = ["text/plain", "application/json", "text/json"]
    if file_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"File type {file_type} not supported. Allowed: {allowed_types}"
        )
    
    return True
