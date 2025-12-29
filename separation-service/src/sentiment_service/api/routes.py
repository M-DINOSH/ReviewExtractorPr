"""
API routes for Sentiment Analysis Service
"""
import time
from typing import List

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address

from sentiment_service.core.config import settings
from sentiment_service.core.logging import get_logger
from sentiment_service.models.schemas import (
    ErrorResponse,
    HealthCheck,
    SentimentAnalysisRequest,
    SentimentAnalysisResponse,
)
from sentiment_service.services.sentiment import sentiment_analyzer

logger = get_logger(__name__)

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Create routers
api_router = APIRouter()
health_router = APIRouter()


# Health check endpoints
@health_router.get("/health", response_model=HealthCheck)
async def health_check():
    """Health check endpoint"""
    import psutil

    # Get system info
    uptime = time.time()

    return HealthCheck(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        timestamp=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        uptime=uptime
    )


@health_router.get("/ready")
async def readiness_check():
    """Readiness check endpoint"""
    return {"status": "ready"}


# Sentiment analysis endpoints
@api_router.post("/analyze", response_model=SentimentAnalysisResponse)
@limiter.limit(f"{settings.rate_limit_requests_per_minute}/minute")
async def analyze_sentiment(
    request: Request,
    analysis_request: SentimentAnalysisRequest,
):
    """Analyze sentiment of reviews"""
    start_time = time.time()

    try:
        # Validate input
        if not analysis_request.reviews:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No reviews provided for analysis"
            )

        if len(analysis_request.reviews) > 1000:  # Reasonable limit
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Too many reviews. Maximum 1000 reviews per request."
            )

        # Analyze sentiments
        results = sentiment_analyzer.analyze_reviews(analysis_request.reviews)

        processing_time = time.time() - start_time

        logger.info(
            f"Processed {len(results)} reviews in {processing_time:.4f}s",
            extra={
                "endpoint": "/analyze",
                "review_count": len(results),
                "processing_time": processing_time,
                "client_ip": request.client.host if request.client else None
            }
        )

        return SentimentAnalysisResponse(
            results=results,
            total_processed=len(results),
            processing_time=processing_time,
            model_used=settings.sentiment_model
        )

    except HTTPException:
        raise
    except Exception as e:
        processing_time = time.time() - start_time
        logger.error(
            f"Sentiment analysis failed: {str(e)}",
            extra={
                "endpoint": "/analyze",
                "processing_time": processing_time,
                "error": str(e)
            },
            exc_info=True
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Sentiment analysis failed"
        )