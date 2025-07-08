from pydantic import BaseSettings, Field
from typing import Optional

class IngestionConfig(BaseSettings):
    # Buffer and batching
    buffer_max_size: int = Field(10000, env="INGESTION_BUFFER_MAX_SIZE")
    batch_size: int = Field(1000, env="INGESTION_BATCH_SIZE")
    batch_timeout_seconds: int = Field(10, env="INGESTION_BATCH_TIMEOUT_SECONDS")

    # Limits
    max_logs_per_run: int = Field(100000, env="INGESTION_MAX_LOGS_PER_RUN")
    max_file_size_mb: int = Field(500, env="INGESTION_MAX_FILE_SIZE_MB")
    max_concurrent_runs: int = Field(10, env="INGESTION_MAX_CONCURRENT_RUNS")
    timeout_seconds: int = Field(3600, env="INGESTION_TIMEOUT_SECONDS")

    # Misc
    enable_tracing: bool = Field(True, env="INGESTION_ENABLE_TRACING")
    enable_metrics: bool = Field(True, env="INGESTION_ENABLE_METRICS")
    log_level: str = Field("INFO", env="INGESTION_LOG_LEVEL")
    
    # Add more ingestion-specific settings as needed
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

# Usage example:
# config = IngestionConfig()
# print(config.buffer_max_size) 