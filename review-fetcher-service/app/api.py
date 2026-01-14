"""
FastAPI routes for Review Fetcher service
Implements Clean Architecture with dependency injection
"""

from fastapi import APIRouter, HTTPException, Depends, status
from typing import Annotated
import logging
import uuid
from datetime import datetime

from app.models import (
    ReviewFetchRequest, ReviewFetchResponse, HealthCheckResponse
)
from app.deque_buffer import BoundedDequeBuffer
from app.kafka_producer import KafkaEventPublisher
from app.config import get_settings
from app.services.google_api import GoogleAPIClient, GoogleAPIError

logger = logging.getLogger(__name__)

# Create router (will be added to FastAPI app in main.py)
router = APIRouter(prefix="/api/v1", tags=["review-fetcher"])


class APIService:
    """
    Service class for API business logic
    Implements Dependency Injection pattern
    """
    
    def __init__(
        self,
        deque_buffer: BoundedDequeBuffer,
        event_publisher: KafkaEventPublisher,
        settings = None
    ):
        self.deque_buffer = deque_buffer
        self.event_publisher = event_publisher
        self.settings = settings or get_settings()
        self.job_tracking: dict = {}  # In-memory job state
        self.google_api_client = GoogleAPIClient()  # Initialize Google API client
    
    async def validate_access_token(self, token: str) -> bool:
        """
        Validate Google OAuth access token
        Uses GoogleAPIClient which handles both mock and real API
        """
        if not token or len(token) < 10:
            return False
        
        try:
            result = await self.google_api_client.validate_token(token)
            logger.info(f"token_validation_result: {result}")
            return result.get("valid", False)
        except Exception as e:
            logger.error(f"token_validation_error: {str(e)} ({type(e).__name__})")
            return False
    
    async def create_fetch_job(self, request: ReviewFetchRequest) -> ReviewFetchResponse:
        """
        Create a new review fetch job
        
        Returns: ReviewFetchResponse with job_id
        Raises: HTTPException on error
        """
        # Validate token
        is_valid = await self.validate_access_token(request.access_token)
        if not is_valid:
            logger.warning("invalid_access_token")
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid access token"
            )
        
        # Generate job ID
        job_id = str(uuid.uuid4())
        
        # Try to enqueue job into deque
        enqueued = await self.deque_buffer.enqueue({
            "job_id": job_id,
            "access_token": request.access_token,
            "created_at": datetime.utcnow().isoformat()
        })
        
        if not enqueued:
            logger.warning("job_enqueue_failed_deque_full job_id=%s", job_id)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Service is at capacity. Please retry after a few seconds."
            )
        
        # Track job
        self.job_tracking[job_id] = {
            "status": "queued",
            "created_at": datetime.utcnow().isoformat(),
            "access_token": request.access_token
        }
        
        logger.info("job_created job_id=%s", job_id)
        
        return ReviewFetchResponse(job_id=job_id)
    
    def get_job_status(self, job_id: str) -> dict:
        """Get current job status"""
        if job_id not in self.job_tracking:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found"
            )
        
        return self.job_tracking.get(job_id, {})
    
    async def get_health(self) -> HealthCheckResponse:
        """Get service health status"""
        deque_load = await self.deque_buffer.get_load_percent()
        
        return HealthCheckResponse(
            status="healthy" if deque_load < 90 else "degraded",
            service=self.settings.service_name,
            version=self.settings.version,
            kafka_connected=True,  # Placeholder
            memory_used_percent=deque_load
        )


# Global API service instance
_api_service: APIService = None


def get_api_service() -> APIService:
    """Dependency injection for API service"""
    global _api_service
    return _api_service


def set_api_service(service: APIService) -> None:
    """Set the global API service instance (called from main.py)"""
    global _api_service
    _api_service = service


@router.post(
    "/review-fetch",
    response_model=ReviewFetchResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Initiate review fetch job",
    description="Submit a Google OAuth token to start fetching reviews"
)
async def fetch_reviews(
    request: ReviewFetchRequest,
    api_service: Annotated[APIService, Depends(get_api_service)]
) -> ReviewFetchResponse:
    """
    POST /api/v1/review-fetch
    
    Accepts a Google OAuth access token and creates an async job
    to fetch reviews from Google Business Profile API.
    
    Returns immediately with job_id (async processing).
    Client can poll /api/v1/status/{job_id} for progress.
    
    Responses:
    - 202: Job queued successfully
    - 400: Invalid request
    - 401: Invalid token
    - 429: Service at capacity
    - 500: Internal error
    """
    return await api_service.create_fetch_job(request)


@router.get(
    "/status/{job_id}",
    response_model=dict,
    summary="Get job status",
    description="Check the status of a review fetch job"
)
async def get_status(
    job_id: str,
    api_service: Annotated[APIService, Depends(get_api_service)]
) -> dict:
    """
    GET /api/v1/status/{job_id}
    
    Get current status of a job.
    
    Status values: queued, processing, completed, failed
    """
    return api_service.get_job_status(job_id)


@router.get(
    "/health",
    response_model=HealthCheckResponse,
    summary="Health check",
    description="Check service health"
)
async def health_check(
    api_service: Annotated[APIService, Depends(get_api_service)]
) -> HealthCheckResponse:
    """
    GET /api/v1/health
    
    Returns service health status.
    
    Used by Kubernetes liveness/readiness probes.
    """
    return await api_service.get_health()


@router.get(
    "/metrics",
    summary="Get service metrics",
    description="Get operational metrics"
)
async def get_metrics(
    api_service: Annotated[APIService, Depends(get_api_service)]
) -> dict:
    """
    GET /api/v1/metrics
    
    Returns service metrics for monitoring.
    """
    deque_metrics = api_service.deque_buffer.get_metrics()
    
    return {
        "deque": deque_metrics,
        "jobs_tracked": len(api_service.job_tracking),
        "timestamp": datetime.utcnow().isoformat()
    }


@router.get(
    "/reviews",
    summary="Get published reviews",
    description="Get all reviews published to reviews-raw topic (mock mode only)"
)
async def get_reviews(
    api_service: Annotated[APIService, Depends(get_api_service)],
    topic: str = "reviews-raw"
) -> dict:
    """
    GET /api/v1/reviews
    
    Returns all reviews that have been published to the reviews-raw Kafka topic.
    Only works in mock mode.
    """
    messages = api_service.event_publisher.producer.get_messages(topic=topic)
    reviews = [msg["message"] for msg in messages if msg.get("topic") == topic]
    
    return {
        "topic": topic,
        "total_reviews": len(reviews),
        "reviews": reviews,
        "timestamp": datetime.utcnow().isoformat()
    }
