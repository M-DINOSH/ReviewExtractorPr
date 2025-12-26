from pydantic import BaseModel
from typing import Optional
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


class ReviewMessage(BaseModel):
    review_id: str
    location_id: str
    account_id: str
    rating: int
    comment: Optional[str]
    reviewer_name: Optional[str]
    create_time: datetime
    source: str = "google"
    ingestion_timestamp: datetime