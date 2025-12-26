from fastapi import FastAPI, Depends, HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession
from app.database import engine, get_db
from app.models import SyncJob, Base
from app.schemas import SyncRequest, SyncResponse
from app.workers.tasks import sync_reviews_task
from app.services.kafka_producer import kafka_producer
from app.services.google_api import google_api_client
from app.config import settings
import structlog
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

    # Start Kafka producer
    kafka_producer.start()


@app.on_event("shutdown")
async def shutdown_event():
    kafka_producer.stop()
    await google_api_client.close()


@app.post("/sync", response_model=SyncResponse)
async def sync_reviews(
    request: SyncRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db)
):
    # Validate access_token (basic expiry check if possible)
    # For now, assume it's valid

    # Create sync job
    sync_job = SyncJob(
        client_id=request.client_id or "unknown",
        request_id=request.request_id,
        correlation_id=request.correlation_id
    )
    db.add(sync_job)
    await db.commit()
    await db.refresh(sync_job)

    # Enqueue background task
    background_tasks.add_task(
        sync_reviews_task,
        request.access_token,
        request.client_id or "unknown",
        sync_job.id
    )

    return SyncResponse(
        job_id=sync_job.id,
        status="pending",
        message="Sync job enqueued"
    )


@app.get("/health")
async def health_check():
    return {"status": "healthy"}