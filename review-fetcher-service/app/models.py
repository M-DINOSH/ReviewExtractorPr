"""
Data models using Pydantic with strict validation
Implements Value Object and Data Transfer Object patterns
"""

from pydantic import BaseModel, Field, validator
from typing import Optional, Any
from enum import Enum
import uuid
from datetime import datetime


class JobStatus(str, Enum):
    """Enum for job lifecycle states"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    DLQ = "dlq"  # Dead Letter Queue


class ReviewFetchRequest(BaseModel):
    """API request model for initiating review fetch"""
    access_token: str = Field(..., min_length=10, description="Google OAuth access token")
    
    @validator("access_token")
    def validate_token_format(cls, v: str) -> str:
        """Validate token is not empty and reasonable length"""
        if not v or len(v.strip()) == 0:
            raise ValueError("access_token cannot be empty")
        return v.strip()
    
    class Config:
        json_schema_extra = {
            "example": {
                "access_token": "ya29.a0AfH6SMBx..."
            }
        }


class ReviewFetchResponse(BaseModel):
    """API response model"""
    job_id: str = Field(description="Unique job identifier")
    status: str = "queued"
    message: str = "Job enqueued for processing"
    
    class Config:
        json_schema_extra = {
            "example": {
                "job_id": "550e8400-e29b-41d4-a716-446655440000",
                "status": "queued",
                "message": "Job enqueued for processing"
            }
        }


class FetchAccountsEvent(BaseModel):
    """Kafka event: initiate accounts fetch"""
    job_id: str
    access_token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class Account(BaseModel):
    """Represents a Google Business account"""
    job_id: str
    account_id: str
    account_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FetchLocationsEvent(BaseModel):
    """Kafka event: fetch locations for account"""
    job_id: str
    account_id: str
    account_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Location(BaseModel):
    """Represents a business location"""
    job_id: str
    account_id: str
    location_id: str
    location_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class FetchReviewsEvent(BaseModel):
    """Kafka event: fetch reviews for location"""
    job_id: str
    account_id: str
    location_id: str
    location_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Review(BaseModel):
    """Raw review from Google API"""
    job_id: str
    review_id: str
    location_id: str
    account_id: str
    rating: int = Field(ge=1, le=5)
    text: str
    reviewer_name: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    reviewed_at: Optional[datetime] = None
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class DLQMessage(BaseModel):
    """Dead Letter Queue message for failed events"""
    original_topic: str
    original_message: dict[str, Any]
    error: str
    error_code: Optional[str] = None
    retry_count: int = 0
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_encoders = {datetime: lambda v: v.isoformat()}


class JobTrackingInfo(BaseModel):
    """In-memory job tracking state"""
    job_id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    status: JobStatus = JobStatus.PENDING
    access_token: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    accounts_fetched: int = 0
    locations_fetched: int = 0
    reviews_fetched: int = 0
    errors: list[str] = Field(default_factory=list)


class RateLimitStatus(BaseModel):
    """Current rate limit status"""
    available_tokens: float
    capacity: float
    refill_rate: float
    last_refill: datetime = Field(default_factory=datetime.utcnow)
    tokens_used: int = 0


class HealthCheckResponse(BaseModel):
    """Service health status"""
    status: str  # "healthy", "degraded", "unhealthy"
    service: str
    version: str
    kafka_connected: bool
    memory_used_percent: float
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    
    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "service": "review-fetcher-service",
                "version": "1.0.0",
                "kafka_connected": True,
                "memory_used_percent": 45.2,
                "timestamp": "2024-01-07T10:30:00Z"
            }
        }
