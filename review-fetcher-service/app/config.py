"""
Configuration management following Singleton and Factory patterns
Supports environment variables with type-safe validation
"""

from pydantic_settings import BaseSettings
from typing import Optional
import os


class KafkaConfig(BaseSettings):
    """Kafka connection settings"""
    bootstrap_servers: str = "localhost:9092"  # comma-separated string
    consumer_group: str = "review-fetcher-service"
    auto_offset_reset: str = "earliest"
    session_timeout_ms: int = 30000
    max_poll_records: int = 100
    
    def get_bootstrap_servers_list(self) -> list[str]:
        """Convert comma-separated string to list"""
        return [s.strip() for s in self.bootstrap_servers.split(",")]
    
    class Config:
        env_prefix = "KAFKA_"


class GoogleAPIConfig(BaseSettings):
    """Google API settings for rate limiting"""
    # Google Business Profile API: 1000 requests per day, 10 per second
    requests_per_second: int = 10
    daily_quota: int = 1000
    
    class Config:
        env_prefix = "GOOGLE_"


class RateLimitConfig(BaseSettings):
    """Rate limiting configuration"""
    token_bucket_capacity: int = 100  # Max burst
    refill_rate: float = 10.0  # Tokens per second
    
    class Config:
        env_prefix = "RATELIMIT_"


class RetryConfig(BaseSettings):
    """Retry policy configuration"""
    max_retries: int = 3
    initial_backoff_ms: int = 100
    max_backoff_ms: int = 10000
    backoff_multiplier: float = 2.0
    
    class Config:
        env_prefix = "RETRY_"


class DequeConfig(BaseSettings):
    """In-memory deque configuration"""
    max_size: int = 10000
    burst_check_interval_sec: float = 0.1
    
    class Config:
        env_prefix = "DEQUE_"


class Settings(BaseSettings):
    """Root settings aggregating all sub-configurations"""
    
    # Service info
    service_name: str = "review-fetcher-service"
    version: str = "1.0.0"
    environment: str = os.getenv("ENVIRONMENT", "development")
    
    # Logging
    log_level: str = os.getenv("LOG_LEVEL", "INFO")
    log_format: str = "json"  # or "text"
    
    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_workers: int = 4
    request_timeout_sec: int = 30
    
    # Sub-configs
    kafka: KafkaConfig = KafkaConfig()
    google_api: GoogleAPIConfig = GoogleAPIConfig()
    rate_limit: RateLimitConfig = RateLimitConfig()
    retry: RetryConfig = RetryConfig()
    deque: DequeConfig = DequeConfig()
    
    # Feature flags
    mock_google_api: bool = os.getenv("MOCK_GOOGLE_API", "true").lower() == "true"
    enable_dlq: bool = True
    enable_idempotency: bool = True
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False
        extra = "ignore"  # Ignore unrelated env vars from shared environments


# Singleton instance
_settings_instance: Optional[Settings] = None


def get_settings() -> Settings:
    """Factory function to get singleton Settings instance (Singleton Pattern)"""
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


# Direct export for backward compatibility
settings = get_settings()