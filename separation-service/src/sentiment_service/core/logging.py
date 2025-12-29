"""
Logging configuration for Sentiment Analysis Service
"""
import logging
import sys
from typing import Optional

from pythonjsonlogger import jsonlogger

from .config import settings


def setup_logging() -> None:
    """Setup structured logging"""
    log_level = getattr(logging, settings.log_level.upper(), logging.INFO)

    # Create logger
    logger = logging.getLogger()
    logger.setLevel(log_level)

    # Remove existing handlers
    for handler in logger.handlers[:]:
        logger.removeHandler(handler)

    # Create formatter
    if settings.log_format == "json":
        formatter = jsonlogger.JsonFormatter(
            "%(asctime)s %(name)s %(levelname)s %(message)s",
            datefmt="%Y-%m-%dT%H:%M:%S%z"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        )

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # Log the configuration
    logger.info(
        "Logging configured",
        extra={
            "log_level": settings.log_level,
            "log_format": settings.log_format,
            "environment": settings.environment,
            "service": "sentiment-service",
            "version": settings.app_version
        }
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance"""
    return logging.getLogger(name)