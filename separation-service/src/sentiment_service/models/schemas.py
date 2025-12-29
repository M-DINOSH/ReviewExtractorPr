"""
Pydantic schemas for API requests and responses
"""
from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class ReviewInput(BaseModel):
    """Input schema for a single review"""
    text: str = Field(..., min_length=1, max_length=5000, description="The review text to analyze")
    id: Optional[str] = Field(None, description="Optional review ID")


class SentimentAnalysisRequest(BaseModel):
    """Request schema for sentiment analysis"""
    reviews: List[ReviewInput] = Field(..., description="List of reviews to analyze")


class SentimentResult(BaseModel):
    """Result schema for sentiment analysis"""
    id: Optional[str] = None
    text: str
    sentiment: str = Field(..., description="POSITIVE, NEGATIVE, or NEUTRAL")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score (0-1)")


class SentimentAnalysisResponse(BaseModel):
    """Response schema for sentiment analysis"""
    results: List[SentimentResult]
    total_processed: int
    processing_time: float
    model_used: str = "vader"


class HealthCheck(BaseModel):
    """Health check response"""
    status: str = "healthy"
    service: str
    version: str
    timestamp: str
    uptime: float


class ErrorResponse(BaseModel):
    """Error response schema"""
    error: str
    message: str
    timestamp: float