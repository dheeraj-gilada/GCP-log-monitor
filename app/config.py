"""
Configuration management for GCP Log Monitoring system.
Handles environment variables and application settings.
"""

import os
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # API Configuration
    openai_api_key: str = Field(..., description="OpenAI API key for GPT-4O")
    sendgrid_api_key: str = Field(..., description="SendGrid API key for email alerts")
    alert_email_from: str = Field(..., description="From email address for alerts")
    
    # GCP Configuration
    gcp_project_id: str = Field(..., description="GCP project ID")
    gcp_service_account_path: Optional[str] = Field(None, description="Path to GCP service account JSON file")
    
    # Application Settings
    app_name: str = Field(default="GCP Log Monitoring", description="Application name")
    app_version: str = Field(default="1.0.0", description="Application version")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Monitoring Configuration
    log_buffer_minutes: int = Field(default=10, description="Log buffer sliding window in minutes")
    max_buffer_size: int = Field(default=10000, description="Maximum number of logs in buffer")
    anomaly_check_interval: int = Field(default=30, description="Anomaly check interval in seconds")
    
    # Anomaly Detection Thresholds
    error_rate_threshold: float = Field(default=0.05, description="Error rate threshold (5%)")
    latency_threshold_ms: int = Field(default=2000, description="Latency threshold in milliseconds")
    repeated_error_threshold: int = Field(default=5, description="Threshold for repeated errors")
    
    # WebSocket Configuration
    websocket_heartbeat_interval: int = Field(default=30, description="WebSocket heartbeat interval")
    
    # Email Configuration
    alert_email_to: Optional[str] = Field(None, description="Default recipient for alerts")
    email_rate_limit_minutes: int = Field(default=15, description="Minimum minutes between similar alerts")
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings."""
    return settings


def validate_gcp_credentials() -> bool:
    """Validate GCP credentials are available."""
    if not settings.gcp_service_account_path:
        return False
    
    if not os.path.exists(settings.gcp_service_account_path):
        return False
    
    return True


def validate_openai_config() -> bool:
    """Validate OpenAI configuration."""
    return bool(settings.openai_api_key and settings.openai_api_key.startswith('sk-'))


def validate_sendgrid_config() -> bool:
    """Validate SendGrid configuration."""
    return bool(settings.sendgrid_api_key and settings.alert_email_from)
