from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from typing import Optional

class BufferConfig(BaseSettings):
    """
    Configuration for the real-time log buffer, Redis, and TimescaleDB integration.
    """
    # Memory buffer
    buffer_max_size: int = Field(1000, env="BUFFER_MAX_SIZE")
    buffer_time_window_minutes: int = Field(10000, env="BUFFER_TIME_WINDOW_MINUTES")
    buffer_cleanup_interval_seconds: int = Field(60, env="BUFFER_CLEANUP_INTERVAL_SECONDS")
    
    # Batching
    buffer_batch_size: int = Field(500, env="BUFFER_BATCH_SIZE")
    buffer_flush_interval_seconds: int = Field(10, env="BUFFER_FLUSH_INTERVAL_SECONDS")
    
    # Retention
    timescale_retention_days: int = Field(90, env="TIMESCALEDB_RETENTION_DAYS")
    timescaledb_retention_days: int = Field(30, env="TIMESCALEDB_RETENTION_DAYS")
    
    # Redis
    enable_redis: bool = Field(True, env="ENABLE_REDIS")
    redis_url: Optional[str] = Field(None, env="REDIS_URL")
    redis_stream_name: str = Field("log_stream", env="REDIS_STREAM_NAME")
    redis_sorted_set_name: str = Field("log_sorted_set", env="REDIS_SORTED_SET_NAME")
    redis_pubsub_channel: str = Field("log_channel", env="REDIS_PUBSUB_CHANNEL")
    redis_connection_timeout: int = Field(5, env="REDIS_CONNECTION_TIMEOUT")
    
    # TimescaleDB
    enable_timescaledb: bool = Field(True, env="ENABLE_TIMESCALEDB")
    timescale_dsn: Optional[str] = Field(None, env="TIMESCALE_DSN")
    timescale_table: str = Field("logs", env="TIMESCALEDB_TABLE_NAME")
    timescale_enabled: bool = Field(True, env="ENABLE_TIMESCALEDB")
    timescale_connection_timeout: int = Field(5, env="TIMESCALEDB_CONNECTION_TIMEOUT")
    
    # Fallback/Resilience
    fallback_mode: str = Field("auto", env="FALLBACK_MODE")
    
    model_config = ConfigDict(extra="allow") 

    @property
    def timescaledb_url(self):
        return self.timescale_dsn 

    @property
    def timescaledb_table_name(self):
        return self.timescale_table 