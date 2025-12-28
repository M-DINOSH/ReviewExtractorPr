from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine, get_db, async_session
from app.models import SyncJob, Base
from app.schemas import SyncRequest, SyncResponse, JobStatusResponse, ReviewsListResponse
from app.workers.tasks import sync_reviews_task
from app.services.kafka_producer import kafka_producer
from app.services.google_api import google_api_client
from app.config import settings
import structlog

logger = structlog.get_logger()
import logging

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

app = FastAPI(title="Google Reviews Fetcher Service", version="1.0.0")


@app.on_event("startup")
async def startup_event():
    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Start Kafka producer (optional for development)
    try:
        kafka_producer.start()
    except Exception as e:
        logger.warning("Failed to start Kafka producer, continuing without it", error=str(e))


@app.on_event("shutdown")
async def shutdown_event():
    kafka_producer.stop()
    await google_api_client.close()


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
                "reviews_fetch": {"status": "pending", "timestamp": None, "message": None},
                "kafka_publish": {"status": "pending", "timestamp": None, "message": None}
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
    return {"status": "healthy"}


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