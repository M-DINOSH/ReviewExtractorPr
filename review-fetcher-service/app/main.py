"""
FastAPI application with SOLID principles and design patterns
"""

from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine, get_db, async_session
from app.models import SyncJob, Base
from app.schemas import SyncRequest, SyncResponse, JobStatusResponse, ReviewsListResponse
from app.workers.tasks import sync_reviews_task
from app.services.simple_sync_service import SimpleSyncService
from app.config import settings
import structlog
import asyncio
from collections import deque
import logging

# Import new OOP components
from app.core.services import BaseService, DequeQueue, service_factory, logger, event_subject
from app.core.interfaces import IService, ServiceStatus, ServiceHealth
from app.commands import SyncReviewsCommand, HealthCheckCommand, CommandInvoker
from app.observers import metrics_observer, logging_observer, alerting_observer, health_observer
from app.strategies import SyncStrategy, SyncStrategyFactory
from app.repositories import SyncJobRepository
from app.decorators import log_execution, rate_limit, monitor_performance, validate_input

# Configure logging
logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

# Global request queue for scaling
request_queue = DequeQueue(max_size=1000)
PROCESSING_RATE = 10  # Requests per second to avoid overwhelming APIs

# Command invoker for handling requests
command_invoker = CommandInvoker()

# Service registry
class ReviewFetcherService(BaseService):
    """Main service implementing IService"""

    def __init__(self):
        super().__init__("review-fetcher", "2.0.0")
        self.queue = request_queue
        self.command_invoker = command_invoker

    async def get_health(self) -> ServiceHealth:
        """Get service health with queue status"""
        base_health = await super().get_health()
        queue_size = await self.queue.size()

        # Determine health status based on queue
        if queue_size > 800:  # 80% capacity
            status = ServiceStatus.UNHEALTHY
        elif queue_size > 500:  # 50% capacity
            status = ServiceStatus.DEGRADED
        else:
            status = ServiceStatus.HEALTHY

        base_health.status = status
        base_health.metrics.update({
            "queue_size": queue_size,
            "queue_max_size": 1000,
            "processing_rate": PROCESSING_RATE
        })

        return base_health

# Create main service instance
review_service = ReviewFetcherService()

async def process_request_queue():
    """Background worker to process queued requests at a controlled rate"""
    while True:
        try:
            async with queue_lock:
                if request_queue:
                    # Get next request from queue
                    request_data = request_queue.popleft()

            if request_data:
                access_token = request_data['access_token']
                future = request_data['future']

                try:
                    # Process the request
                    service = SimpleSyncService()
                    result = await service.sync_reviews(access_token)

                    # Set the result in the future
                    if not future.done():
                        future.set_result(result)

                    logger.info("Processed queued request", queue_size=len(request_queue))

                except Exception as e:
                    logger.error("Failed to process queued request", error=str(e))
                    if not future.done():
                        future.set_exception(e)

            # Control processing rate to prevent overwhelming APIs
            await asyncio.sleep(1.0 / PROCESSING_RATE)

        except Exception as e:
            logger.error("Queue processing error", error=str(e))
            await asyncio.sleep(1)  # Brief pause on error

app = FastAPI(title="Google Reviews Fetcher Service", version="2.0.0")


@app.on_event("startup")
async def startup_event():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Register observers
    event_subject.attach(metrics_observer)
    event_subject.attach(logging_observer)
    event_subject.attach(alerting_observer)
    event_subject.attach(health_observer)

    # Register service in factory
    service_factory.register_service("review_fetcher", ReviewFetcherService)

    # Start the request queue processor
    asyncio.create_task(process_request_queue())
    logger.info("Request queue processor started", processing_rate=PROCESSING_RATE)

    # Notify startup
    await event_subject.notify("service_started", {
        "service": "review-fetcher",
        "version": "2.0.0"
    })


@app.on_event("shutdown")
async def shutdown_event():
    # Shutdown main service
    await review_service.shutdown()

    # Notify shutdown
    await event_subject.notify("service_shutdown", {
        "service": "review-fetcher",
        "version": "2.0.0"
    })


@app.post("/sync", response_model=SyncResponse)
async def sync_reviews(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
):
    # Create sync job with access token stored for background processing
    # Use a new session for this operation to avoid dependency injection issues
    db = async_session()
    try:
        sync_job = SyncJob(
            client_id=request.client_id or "unknown",
            request_id=request.request_id,
            correlation_id=request.correlation_id,
            access_token=request.access_token,  # Store token for background processing
            status="pending",
            current_step="token_validation",
            step_status={
                "token_validation": {"status": "pending", "timestamp": None, "message": None},
                "accounts_fetch": {"status": "pending", "timestamp": None, "message": None},
                "locations_fetch": {"status": "pending", "timestamp": None, "message": None},
                "reviews_fetch": {"status": "pending", "timestamp": None, "message": None}
            }
        )
        db.add(sync_job)
        await db.commit()
        await db.refresh(sync_job)
    finally:
        await db.close()

    # Enqueue background task with continuous flow
    background_tasks.add_task(
        sync_reviews_task,
        request.access_token,
        request.client_id or "unknown",
        sync_job.id
    )

    return SyncResponse(
        job_id=sync_job.id,
        status="pending",
        message="Continuous sync flow initiated - will automatically progress through all steps"
    )


@app.get("/job/{job_id}", response_model=JobStatusResponse)
async def get_job_status(job_id: int):
    """Get the status of a sync job including step-by-step progress"""
    db = async_session()
    try:
        job = await db.get(SyncJob, job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")

        return JobStatusResponse(
            job_id=job.id,
            status=job.status,
            current_step=job.current_step,
            step_status=job.step_status or {},
            created_at=job.created_at,
            updated_at=job.updated_at
        )
    finally:
        await db.close()


@app.get("/health")
async def health_check():
    """Enhanced health check using service pattern and observer monitoring"""
    # Get main service health
    service_health = await review_service.get_health()

    # Get observer health data
    observer_health = health_observer.get_health_status()
    metrics = metrics_observer.get_metrics()

    return {
        "status": service_health.status.value,
        "service": service_health.name,
        "version": service_health.version,
        "timestamp": asyncio.get_event_loop().time(),
        "uptime": service_health.uptime,
        "queue": service_health.metrics,
        "services": observer_health.get("services", {}),
        "metrics": metrics
    }


@app.get("/reviews", response_model=ReviewsListResponse)
async def get_all_reviews(limit: int = 100, offset: int = 0):
    """Get all reviews from the database with pagination"""
    from app.models import Review
    from sqlalchemy import text

    db = async_session()
    try:
        # Get total count
        count_query = await db.execute(text("SELECT COUNT(*) FROM reviews"))
        total_reviews = count_query.scalar()

        # Get reviews with pagination
        reviews_query = await db.execute(
            text("""
                SELECT id, location_id, account_id, rating, comment, reviewer_name, create_time, client_id, sync_job_id, created_at
                FROM reviews
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"limit": limit, "offset": offset}
        )
        review_rows = reviews_query.fetchall()

        reviews = []
        for row in review_rows:
            reviews.append({
                "id": row[0],
                "location_id": row[1],
                "account_id": row[2],
                "rating": row[3],
                "comment": row[4],
                "reviewer_name": row[5],
                "create_time": row[6],
                "client_id": row[7],
                "sync_job_id": row[8],
                "created_at": row[9]
            })

        return ReviewsListResponse(
            total_reviews=total_reviews,
            reviews=reviews
        )
    finally:
        await db.close()


@app.get("/reviews/{job_id}", response_model=ReviewsListResponse)
async def get_reviews_by_job(job_id: int, limit: int = 100, offset: int = 0):
    """Get reviews for a specific sync job"""
    from app.models import Review
    from sqlalchemy import text

    db = async_session()
    try:
        # Get total count for this job
        count_query = await db.execute(
            text("SELECT COUNT(*) FROM reviews WHERE sync_job_id = :job_id"),
            {"job_id": job_id}
        )
        total_reviews = count_query.scalar()

        # Get reviews for this job with pagination
        reviews_query = await db.execute(
            text("""
                SELECT id, location_id, account_id, rating, comment, reviewer_name, create_time, client_id, sync_job_id, created_at
                FROM reviews
                WHERE sync_job_id = :job_id
                ORDER BY created_at DESC
                LIMIT :limit OFFSET :offset
            """),
            {"job_id": job_id, "limit": limit, "offset": offset}
        )
        review_rows = reviews_query.fetchall()

        reviews = []
        for row in review_rows:
            reviews.append({
                "id": row[0],
                "location_id": row[1],
                "account_id": row[2],
                "rating": row[3],
                "comment": row[4],
                "reviewer_name": row[5],
                "create_time": row[6],
                "client_id": row[7],
                "sync_job_id": row[8],
                "created_at": row[9]
            })

        return ReviewsListResponse(
            total_reviews=total_reviews,
            reviews=reviews
        )
    finally:
        await db.close()

@app.get("/sync/reviews")
@log_execution()
@rate_limit(requests_per_minute=60)
@monitor_performance(threshold_ms=5000)
@validate_input({"access_token": str})
async def sync_reviews(access_token: str, request_id: str = "auto"):
    """
    Simplified sync endpoint that returns combined JSON data directly.

    This endpoint provides a streamlined flow that:
    1. Accepts only an access_token
    2. Automatically fetches accounts, locations, and reviews
    3. Returns combined JSON without database persistence or Kafka

    Uses a request queue for automatic scaling with incoming user requests.
    Implements SOLID principles with command pattern and observer notifications.

    Query Parameters:
    - access_token: OAuth access token (required)
    - request_id: Optional request identifier for tracking

    Returns:
    {
        "account": {...},
        "locations": [
            {
                "location": {...},
                "reviews": [...]
            }
        ]
    }
    """
    # Notify request started
    await event_subject.notify("request_started", {
        "request_id": request_id,
        "endpoint": "/sync/reviews",
        "access_token": access_token[:10] + "..."
    })

    try:
        # Check queue size to prevent overload
        queue_size = await request_queue.size()
        if queue_size >= 1000:
            await event_subject.notify("queue_full", {
                "request_id": request_id,
                "queue_size": queue_size
            })
            raise HTTPException(
                status_code=429,
                detail=f"Service temporarily overloaded. Queue size: {queue_size}. Please try again later."
            )

        # Create sync service with strategy pattern
        strategy = SyncStrategyFactory.create_strategy(SyncStrategy.SIMPLE)
        sync_service = SimpleSyncService()
        sync_service.strategy = strategy  # Inject strategy

        # Create and execute command
        command = SyncReviewsCommand(sync_service, access_token)
        result = await command_invoker.execute_command(command)

        # Notify success
        await event_subject.notify("request_completed", {
            "request_id": request_id,
            "result_size": len(str(result))
        })

        return result

    except HTTPException:
        raise
    except Exception as e:
        # Notify error
        await event_subject.notify("request_error", {
            "request_id": request_id,
            "error": str(e)
        })
