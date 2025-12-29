"""
Configuration management for Sentiment Analysis Service
"""
import os
from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings with environment variable support"""

    # Application
    app_name: str = "Sentiment Analysis Service"
    app_version: str = "1.0.0"
    debug: bool = False
    environment: str = "development"

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    workers: int = 1
    reload: bool = False

    # Rate Limiting
    rate_limit_requests_per_minute: int = 100

    # Sentiment Analysis
    sentiment_model: str = "vader"  # vader, textblob, transformers
    sentiment_batch_size: int = 10

    # Monitoring
    metrics_enabled: bool = True
    metrics_port: int = 9090

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"  # json or text

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


settings = Settings()