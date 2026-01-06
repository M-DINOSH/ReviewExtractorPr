"""
FastAPI application with SOLID principles and design patterns
"""

from fastapi import FastAPI, HTTPException
from app.services.simple_sync_service import SimpleSyncService
from app.config import settings
import structlog
import asyncio
import logging

# Import new OOP components
from app.core.services import BaseService, DequeQueue, service_factory, logger, event_subject
from app.core.interfaces import IService, ServiceStatus, ServiceHealth
from app.commands import SyncReviewsCommand, HealthCheckCommand, CommandInvoker
from app.observers import metrics_observer, logging_observer, alerting_observer, health_observer
from app.strategies import SyncStrategy, SyncStrategyFactory
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

app = FastAPI(title="Google Reviews Fetcher Service", version="2.0.0")


@app.on_event("startup")
async def startup_event():
    # Register observers
    event_subject.attach(metrics_observer)
    event_subject.attach(logging_observer)
    event_subject.attach(alerting_observer)
    event_subject.attach(health_observer)

    # Register service in factory
    service_factory.register_service("review_fetcher", ReviewFetcherService)

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


@app.get("/sync/reviews")
@log_execution()
@rate_limit(requests_per_minute=60)
@monitor_performance(threshold_ms=5000)
@validate_input({"access_token": str})
async def sync_reviews(access_token: str, request_id: str = "auto"):
    """
    Production Google Reviews API endpoint that returns combined JSON data directly.

    This endpoint provides a streamlined flow that:
    1. Accepts only an access_token (Google OAuth token)
    2. Automatically fetches accounts, locations, and reviews from Google API
    3. Returns combined JSON without database persistence

    Uses a request queue for automatic scaling with incoming user requests.
    Implements SOLID principles with command pattern and observer notifications.

    Query Parameters:
    - access_token: Google OAuth access token (required, must start with 'ya29.')
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
