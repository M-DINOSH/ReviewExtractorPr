from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime


class SyncRequest(BaseModel):
    access_token: str
    client_id: Optional[str] = None
    request_id: Optional[str] = None
    correlation_id: Optional[str] = None


class SyncResponse(BaseModel):
    job_id: int
    status: str
    message: str


class JobStatusResponse(BaseModel):
    job_id: int
    status: str
    current_step: str
    step_status: Dict[str, Any]
    created_at: datetime
    updated_at: Optional[datetime]


class ReviewMessage(BaseModel):
    review_id: str
    location_id: str
    account_id: str
    rating: Optional[int]
    comment: Optional[str]
    reviewer_name: Optional[str]
    create_time: Optional[str]
    source: str = "google"
    ingestion_timestamp: str
    sync_job_id: int


class ReviewResponse(BaseModel):
    id: str
    location_id: str
    account_id: str
    rating: Optional[int]
    comment: Optional[str]
    reviewer_name: Optional[str]
    create_time: Optional[datetime]
    client_id: str
    sync_job_id: int
    created_at: datetime


class ReviewsListResponse(BaseModel):
    total_reviews: int
    reviews: list[ReviewResponse]