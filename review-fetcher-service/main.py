"""
FastAPI application orchestrator
Moved to service root for app-level entrypoint
"""

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.models import HealthCheckResponse
from app.api import router as api_router, APIService, set_api_service
from app.token_management.routes import token_router
from app.token_management.database import init_databases, close_databases
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
    """Container for application state"""

    def __init__(self):
        self.settings = get_settings()
        self.deque_buffer: Optional[BoundedDequeBuffer] = None
        self.kafka_producer: Optional[KafkaProducerFactory] = None
        self.event_publisher: Optional[KafkaEventPublisher] = None
        self.api_service: Optional[APIService] = None

        self.account_rate_limiter: Optional[TokenBucketLimiter] = None
        self.location_rate_limiter: Optional[TokenBucketLimiter] = None
        self.review_rate_limiter: Optional[TokenBucketLimiter] = None

        self.retry_scheduler: Optional[RetryScheduler] = None

        self.account_worker: Optional[AccountWorker] = None
        self.location_worker: Optional[LocationWorker] = None
        self.review_worker: Optional[ReviewWorker] = None

        self.producer_task: Optional[asyncio.Task] = None
        self.retry_task: Optional[asyncio.Task] = None
        self.workers_task: Optional[asyncio.Task] = None


_app_state: Optional[AppState] = None


def get_app_state() -> AppState:
    global _app_state
    return _app_state


async def initialize_components() -> AppState:
    state = AppState()
    logger.info("initializing_application_components")

    init_databases()
    logger.info("databases_initialized")

    state.deque_buffer = BoundedDequeBuffer(max_size=state.settings.deque.max_size)
    logger.info("deque_buffer_initialized max_size=%s", state.settings.deque.max_size)

    producer = KafkaProducerFactory.create(
        mock=state.settings.mock_kafka,
        bootstrap_servers=state.settings.kafka.get_bootstrap_servers_list(),
    )
    await producer.connect()
    state.kafka_producer = producer
    logger.info("kafka_producer_initialized")

    state.event_publisher = KafkaEventPublisher(producer)
    logger.info("event_publisher_initialized")

    state.account_rate_limiter = TokenBucketLimiter(
        capacity=state.settings.rate_limit.token_bucket_capacity,
        refill_rate=state.settings.rate_limit.refill_rate,
    )
    state.location_rate_limiter = TokenBucketLimiter(
        capacity=state.settings.rate_limit.token_bucket_capacity,
        refill_rate=state.settings.rate_limit.refill_rate,
    )
    state.review_rate_limiter = TokenBucketLimiter(
        capacity=state.settings.rate_limit.token_bucket_capacity,
        refill_rate=state.settings.rate_limit.refill_rate,
    )
    logger.info("rate_limiters_initialized")

    retry_policy = ExponentialBackoffPolicy(
        max_retries=state.settings.retry.max_retries,
        initial_backoff_ms=state.settings.retry.initial_backoff_ms,
        max_backoff_ms=state.settings.retry.max_backoff_ms,
        multiplier=state.settings.retry.backoff_multiplier,
    )
    state.retry_scheduler = RetryScheduler(policy=retry_policy)
    logger.info("retry_scheduler_initialized")

    state.account_worker = AccountWorker(
        rate_limiter=state.account_rate_limiter,
        retry_scheduler=state.retry_scheduler,
        event_publisher=state.event_publisher,
        mock_mode=state.settings.mock_kafka,
        bootstrap_servers=state.settings.kafka.get_bootstrap_servers_list(),
    )
    state.location_worker = LocationWorker(
        rate_limiter=state.location_rate_limiter,
        retry_scheduler=state.retry_scheduler,
        event_publisher=state.event_publisher,
        mock_mode=state.settings.mock_kafka,
        bootstrap_servers=state.settings.kafka.get_bootstrap_servers_list(),
    )
    state.review_worker = ReviewWorker(
        rate_limiter=state.review_rate_limiter,
        retry_scheduler=state.retry_scheduler,
        event_publisher=state.event_publisher,
        mock_mode=state.settings.mock_kafka,
        bootstrap_servers=state.settings.kafka.get_bootstrap_servers_list(),
    )
    logger.info("kafka_workers_initialized")

    state.api_service = APIService(
        deque_buffer=state.deque_buffer,
        event_publisher=state.event_publisher,
        settings=state.settings,
    )
    logger.info("api_service_initialized")

    return state


async def start_background_tasks(state: AppState) -> None:
    async def producer_loop():
        logger.info("producer_loop_started")
        try:
            while True:
                if state.event_publisher:
                    batch = await state.deque_buffer.dequeue_batch(batch_size=100)
                    for job in batch:
                        success = await state.event_publisher.publish_fetch_accounts_event(
                            job_id=job["job_id"], access_token=job["access_token"]
                        )
                        if success:
                            logger.info("job_published_to_kafka job_id=%s", job["job_id"])
                        else:
                            logger.error("job_publish_failed job_id=%s", job["job_id"])
                await asyncio.sleep(state.settings.deque.burst_check_interval_sec)
        except Exception as e:
            logger.error("producer_loop_error %s", str(e))

    async def retry_loop():
        logger.info("retry_loop_started")
        try:
            while True:
                ready_tasks = await state.retry_scheduler.get_ready_tasks()
                for task in ready_tasks:
                    message_type = task.payload.get("type")
                    if message_type == "fetch_accounts":
                        await state.event_publisher.publish_fetch_accounts_event(
                            job_id=task.payload["job_id"], access_token=task.payload["access_token"]
                        )
                    elif message_type == "fetch_locations":
                        await state.event_publisher.publish_fetch_locations_event(
                            job_id=task.payload["job_id"],
                            account_id=task.payload["account_id"],
                            account_name=task.payload.get("account_name", ""),
                        )
                    elif message_type == "fetch_reviews":
                        await state.event_publisher.publish_fetch_reviews_event(
                            job_id=task.payload["job_id"],
                            account_id=task.payload["account_id"],
                            location_id=task.payload["location_id"],
                            location_name=task.payload.get("location_name", ""),
                        )
                    await state.retry_scheduler.mark_retry_end(task.message_id)
                await asyncio.sleep(1.0)
        except Exception as e:
            logger.error("retry_loop_error %s", str(e))

    async def workers_loop():
        logger.info("workers_loop_started")
        try:
            await asyncio.gather(
                state.account_worker.run(),
                state.location_worker.run(),
                state.review_worker.run(),
                return_exceptions=True,
            )
        except Exception as e:
            logger.error("workers_loop_error %s", str(e))

    state.producer_task = asyncio.create_task(producer_loop())
    state.retry_task = asyncio.create_task(retry_loop())
    state.workers_task = asyncio.create_task(workers_loop())
    logger.info("background_tasks_started")


async def shutdown_background_tasks(state: AppState) -> None:
    logger.info("stopping_background_tasks")
    if state.producer_task:
        state.producer_task.cancel()
    if state.retry_task:
        state.retry_task.cancel()
    if state.workers_task:
        state.workers_task.cancel()

    if state.account_worker:
        await state.account_worker.stop()
    if state.location_worker:
        await state.location_worker.stop()
    if state.review_worker:
        await state.review_worker.stop()

    if state.kafka_producer:
        await state.kafka_producer.disconnect()

    close_databases()
    logger.info("background_tasks_stopped")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("application_startup")
    global _app_state
    _app_state = await initialize_components()
    await start_background_tasks(_app_state)
    app.state.app_state = _app_state
    set_api_service(_app_state.api_service)
    yield
    logger.info("application_shutdown")
    await shutdown_background_tasks(_app_state)


def create_app() -> FastAPI:
    settings = get_settings()
    logging.basicConfig(level=getattr(logging, settings.log_level.upper()))
    app = FastAPI(
        title=settings.service_name,
        version=settings.version,
        description="Production-ready Review Fetcher microservice",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(api_router)
    app.include_router(token_router)
    app.include_router(demo_router)

    @app.get("/", include_in_schema=False)
    async def root():
        return {
            "service": settings.service_name,
            "version": settings.version,
            "status": "running",
            "docs": "/docs",
        }
    return app


app = create_app()