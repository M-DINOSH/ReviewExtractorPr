"""
Database configuration for Token Management (single database with multiple tables)
"""
import os
import logging
from typing import Generator
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

logger = logging.getLogger(__name__)

# Single database URL (falls back to legacy env vars for compatibility)
DATABASE_URL = (
    os.getenv("TOKEN_MANAGEMENT_DATABASE_URL")
    or os.getenv("CLIENT_DATABASE_URL")
    or os.getenv("TOKEN_DATABASE_URL")
    or "postgresql://token_user:token_password@localhost:5435/token_service_db"
)

# Engine and session factory
engine = create_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Declarative base for all token management tables
Base = declarative_base()

# Legacy aliases maintained for backward compatibility
ClientBase = Base
TokenBase = Base
client_engine = engine
token_engine = engine
ClientSessionLocal = SessionLocal
TokenSessionLocal = SessionLocal
CLIENT_DATABASE_URL = DATABASE_URL
TOKEN_DATABASE_URL = DATABASE_URL


def get_db() -> Generator[Session, None, None]:
    """Dependency: token management DB session"""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# Backward-compatible aliases (both use the same database now)
def get_client_db() -> Generator[Session, None, None]:
    yield from get_db()


def get_token_db() -> Generator[Session, None, None]:
    yield from get_db()


def init_db() -> None:
    """Create all token management tables"""
    logger.info("Initializing token management database...")
    from app.token_management.models.client import Client  # noqa: F401
    from app.token_management.models.token import Token  # noqa: F401
    Base.metadata.create_all(bind=engine)
    logger.info("Token management database initialized successfully")


def close_db() -> None:
    logger.info("Closing token management database connections...")
    engine.dispose()
    logger.info("Token management database connections closed")


# Backward-compatible helpers
def init_databases() -> None:
    init_db()


def close_databases() -> None:
    close_db()


def get_database_url() -> str:
    """Get database URL for Alembic"""
    return DATABASE_URL


def get_client_database_url() -> str:
    return DATABASE_URL


def get_token_database_url() -> str:
    return DATABASE_URL
