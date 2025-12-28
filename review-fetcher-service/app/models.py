from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, ForeignKey, Index, JSON
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.sql import func

Base = declarative_base()


class SyncJob(Base):
    __tablename__ = "sync_jobs"

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String, nullable=False)
    request_id = Column(String, nullable=True)
    correlation_id = Column(String, nullable=True)
    status = Column(String, default="pending")  # pending, running, completed, failed
    current_step = Column(String, default="token_validation")  # token_validation, accounts_fetch, locations_fetch, reviews_fetch, kafka_publish
    step_status = Column(JSON, default=dict)  # Track status of each step
    access_token = Column(Text, nullable=False)  # Store token for background processing
    retry_count = Column(Integer, default=0)
    max_retries = Column(Integer, default=3)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_sync_jobs_status', 'status'),
        Index('idx_sync_jobs_client_id', 'client_id'),
        Index('idx_sync_jobs_current_step', 'current_step'),
    )


class Account(Base):
    __tablename__ = "accounts"

    id = Column(String, primary_key=True)  # Google account ID
    name = Column(String)
    client_id = Column(String, nullable=False)
    sync_job_id = Column(Integer, ForeignKey("sync_jobs.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Location(Base):
    __tablename__ = "locations"

    id = Column(String, primary_key=True)  # Google location ID
    account_id = Column(String, ForeignKey("accounts.id"))
    name = Column(String)
    address = Column(Text)
    client_id = Column(String, nullable=False)
    sync_job_id = Column(Integer, ForeignKey("sync_jobs.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Review(Base):
    __tablename__ = "reviews"

    id = Column(String, primary_key=True)  # Google review ID
    location_id = Column(String, ForeignKey("locations.id"))
    account_id = Column(String, ForeignKey("accounts.id"))
    rating = Column(Integer)
    comment = Column(Text)
    reviewer_name = Column(String)
    create_time = Column(DateTime(timezone=True))
    client_id = Column(String, nullable=False)
    sync_job_id = Column(Integer, ForeignKey("sync_jobs.id"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_reviews_location_id', 'location_id'),
        Index('idx_reviews_account_id', 'account_id'),
        Index('idx_reviews_client_id', 'client_id'),
    )