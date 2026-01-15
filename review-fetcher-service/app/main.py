"""
FastAPI application orchestrator
Manages startup/shutdown lifecycle and component initialization
Implements Dependency Injection and Service Locator patterns
"""

import asyncio
import logging
import structlog
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import HealthCheckResponse
from app.api import router as api_router, APIService, set_api_service
from app.deque_buffer import BoundedDequeBuffer
from app.kafka_producer import KafkaProducerFactory, KafkaEventPublisher
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler, ExponentialBackoffPolicy
from app.kafka_consumers.account_worker import AccountWorker
from app.kafka_consumers.location_worker import LocationWorker
from app.kafka_consumers.review_worker import ReviewWorker
from app.demo_web import router as demo_router

logger = logging.getLogger(__name__)


class AppState: 
    """
    Container for application state
    Implements Service Locator pattern
    """
    
    def __init__(self): 
        self.settings = get_settings()
        self.deque_buffer: Optional[BoundedDequeBuffer] = None
        self.kafka_producer: Optional[KafkaProducerFactory] = None
        self.event_publisher: Optional[KafkaEventPublisher] = None
        self.api_service: Optional[APIService] = None
        
        # Rate limiters per worker
        self.account_rate_limiter: Optional[TokenBucketLimiter] = None
        self.location_rate_limiter: Optional[TokenBucketLimiter] = None
        self.review_rate_limiter: Optional[TokenBucketLimiter] = None
        
        # Retry schedulers
        self.retry_scheduler: Optional[RetryScheduler] = None
        
        # Kafka workers
        self.account_worker: Optional[AccountWorker] = None
        self.location_worker: Optional[LocationWorker] = None
        self.review_worker: Optional[ReviewWorker] = None
        
        # Background tasks
        self.producer_task: Optional[asyncio.Task] = None
        self.retry_task: Optional[asyncio.Task] = None
        self.workers_task: Optional[asyncio.Task] = None


# Global app state
_app_state: Optional[AppState] = None


def get_app_state() -> AppState:
    """Get global app state"""
    global _app_state
    return _app_state


async def initialize_components() -> AppState:
    """
    Initialize all application components
    Implements Factory Pattern
    """
    state = AppState()
    
    logger.info("initializing_application_components")
    
    # 1. Initialize deque buffer
    state.deque_buffer = BoundedDequeBuffer(
        max_size=state.settings.deque.max_size
    )
    logger.info("deque_buffer_initialized max_size=%s", state.settings.deque.max_size)
    
    # 2. Initialize Kafka producer
    # Use mock Kafka only when explicitly enabled; default is real Kafka even in mock data mode
    producer = KafkaProducerFactory.create(
        mock=state.settings.mock_kafka,
        bootstrap_servers=state.settings.kafka.get_bootstrap_servers_list()
    )
    await producer.connect()
    state.kafka_producer = producer
    logger.info("kafka_producer_initialized")
    
    # 3. Initialize event publisher
    state.event_publisher = KafkaEventPublisher(producer)
    logger.info("event_publisher_initialized")
    
    # 4. Initialize rate limiters (per worker)
    state.account_rate_limiter = TokenBucketLimiter(
        capacity=state.settings.rate_limit.token_bucket_capacity,
        refill_rate=state.settings.rate_limit.refill_rate
    )
    state.location_rate_limiter = TokenBucketLimiter(
        capacity=state.settings.rate_limit.token_bucket_capacity,
        refill_rate=state.settings.rate_limit.refill_rate
    )
    state.review_rate_limiter = TokenBucketLimiter(
        capacity=state.settings.rate_limit.token_bucket_capacity,
        refill_rate=state.settings.rate_limit.refill_rate
    )
    logger.info("rate_limiters_initialized")
    
    # 5. Initialize retry scheduler
    retry_policy = ExponentialBackoffPolicy(
        max_retries=state.settings.retry.max_retries,
        initial_backoff_ms=state.settings.retry.initial_backoff_ms,
        max_backoff_ms=state.settings.retry.max_backoff_ms,
        multiplier=state.settings.retry.backoff_multiplier
    )
    state.retry_scheduler = RetryScheduler(policy=retry_policy)
    logger.info("retry_scheduler_initialized")
    
    # 6. Initialize Kafka workers
    state.account_worker = AccountWorker(
        rate_limiter=state.account_rate_limiter,
        retry_scheduler=state.retry_scheduler,
        event_publisher=state.event_publisher,
        mock_mode=state.settings.mock_kafka,
        bootstrap_servers=state.settings.kafka.get_bootstrap_servers_list()
    )
    
    state.location_worker = LocationWorker(
        rate_limiter=state.location_rate_limiter,
        retry_scheduler=state.retry_scheduler,
        event_publisher=state.event_publisher,
        mock_mode=state.settings.mock_kafka,
        bootstrap_servers=state.settings.kafka.get_bootstrap_servers_list()
    )
    
    state.review_worker = ReviewWorker(
        rate_limiter=state.review_rate_limiter,
        retry_scheduler=state.retry_scheduler,
        event_publisher=state.event_publisher,
        mock_mode=state.settings.mock_kafka,
        bootstrap_servers=state.settings.kafka.get_bootstrap_servers_list()
    )
    logger.info("kafka_workers_initialized")
    
    # 7. Initialize API service
    state.api_service = APIService(
        deque_buffer=state.deque_buffer,
        event_publisher=state.event_publisher,
        settings=state.settings
    )
    logger.info("api_service_initialized")
    
    return state


async def start_background_tasks(state: AppState) -> None:
    """Start background worker tasks"""
    
    # Producer task: drain deque and publish to Kafka
    async def producer_loop():
        """Drain deque and publish fetch-accounts events"""
        logger.info("producer_loop_started")
        try:
            while True:
                # Check rate limit
                if state.event_publisher:
                    batch = await state.deque_buffer.dequeue_batch(batch_size=100)
                    
                    for job in batch:
                        success = await state.event_publisher.publish_fetch_accounts_event(
                            job_id=job["job_id"],
                            access_token=job["access_token"]
                        )
                        
                        if success:
                            logger.info("job_published_to_kafka job_id=%s", job["job_id"])
                        else:
                            logger.error("job_publish_failed job_id=%s", job["job_id"])
                
                await asyncio.sleep(state.settings.deque.burst_check_interval_sec)
        except Exception as e:
            logger.error("producer_loop_error %s", str(e))
    
    # Retry task: process retries from retry scheduler
    async def retry_loop():
        """Process scheduled retries"""
        logger.info("retry_loop_started")
        try:
            while True:
                # Get ready tasks
                ready_tasks = await state.retry_scheduler.get_ready_tasks()
                
                for task in ready_tasks:
                    # Re-publish to appropriate topic based on message type
                    message_type = task.payload.get("type")
                    
                    if message_type == "fetch_accounts":
                        await state.event_publisher.publish_fetch_accounts_event(
                            job_id=task.payload["job_id"],
                            access_token=task.payload["access_token"]
                        )
                    elif message_type == "fetch_locations":
                        await state.event_publisher.publish_fetch_locations_event(
                            job_id=task.payload["job_id"],
                            account_id=task.payload["account_id"],
                            account_name=task.payload.get("account_name", "")
                        )
                    elif message_type == "fetch_reviews":
                        await state.event_publisher.publish_fetch_reviews_event(
                            job_id=task.payload["job_id"],
                            account_id=task.payload["account_id"],
                            location_id=task.payload["location_id"],
                            location_name=task.payload.get("location_name", "")
                        )
                    
                    await state.retry_scheduler.mark_retry_end(task.message_id)
                
                await asyncio.sleep(1.0)
        except Exception as e:
            logger.error("retry_loop_error %s", str(e))
    
    # Workers task: start Kafka consumers
    async def workers_loop():
        """Run all Kafka workers concurrently"""
        logger.info("workers_loop_started")
        try:
            await asyncio.gather(
                state.account_worker.run(),
                state.location_worker.run(),
                state.review_worker.run(),
                return_exceptions=True
            )
        except Exception as e:
            logger.error("workers_loop_error %s", str(e))
    
    # Create and store tasks
    state.producer_task = asyncio.create_task(producer_loop())
    state.retry_task = asyncio.create_task(retry_loop())
    state.workers_task = asyncio.create_task(workers_loop())
    
    logger.info("background_tasks_started")


async def shutdown_background_tasks(state: AppState) -> None:
    """Stop background tasks gracefully"""
    logger.info("stopping_background_tasks")
    
    if state.producer_task:
        state.producer_task.cancel()
    if state.retry_task:
        state.retry_task.cancel()
    if state.workers_task:
        state.workers_task.cancel()
    
    # Stop workers
    if state.account_worker:
        await state.account_worker.stop()
    if state.location_worker:
        await state.location_worker.stop()
    if state.review_worker:
        await state.review_worker.stop()
    
    # Close producer
    if state.kafka_producer:
        await state.kafka_producer.disconnect()
    
    logger.info("background_tasks_stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    FastAPI lifespan context manager
    Handles startup and shutdown events
    """
    # Startup
    logger.info("application_startup")
    global _app_state
    _app_state = await initialize_components()
    await start_background_tasks(_app_state)
    app.state.app_state = _app_state
    set_api_service(_app_state.api_service)
    
    yield
    
    # Shutdown
    logger.info("application_shutdown")
    await shutdown_background_tasks(_app_state)


def create_app() -> FastAPI:
    """
    Factory function to create and configure FastAPI application
    """
    settings = get_settings()
    
    # Configure logging
    logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
    
    app = FastAPI(
        title=settings.service_name,
        version=settings.version,
        description="Production-ready Review Fetcher microservice",
        lifespan=lifespan
    )
    
    # Add CORS middleware
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    
    # Include API routes
    app.include_router(api_router)
    app.include_router(demo_router)
    
    # Root endpoint
    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": settings.service_name,
            "version": settings.version,
            "status": "running",
            "docs": "/docs"
        }
    
    return app


# Create app instance
app = create_app()