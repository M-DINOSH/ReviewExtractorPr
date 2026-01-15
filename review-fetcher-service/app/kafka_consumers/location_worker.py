"""Location Worker - Consumes fetch-locations and publishes fetch-reviews.

Uses GoogleAPIClient which supports both mock data (jsom/) and the real Google APIs.
"""

import asyncio
from typing import Optional
import structlog

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler
from app.kafka_producer import KafkaEventPublisher
from app.services.google_api import google_api_client

logger = structlog.get_logger()


class LocationWorker:
    """Consumes fetch-locations events and publishes fetch-reviews events"""
    
    def __init__(
        self,
        rate_limiter: TokenBucketLimiter,
        retry_scheduler: RetryScheduler,
        event_publisher: KafkaEventPublisher,
        mock_mode: bool = True,
        bootstrap_servers: Optional[list[str]] = None
    ):
        self.rate_limiter = rate_limiter
        self.retry_scheduler = retry_scheduler
        self.event_publisher = event_publisher
        self.mock_mode = mock_mode
        self.bootstrap_servers = bootstrap_servers or ["localhost:9092"]
        self.consumer = None
        self._setup_consumer()
    
    def _setup_consumer(self) -> None:
        """Create consumer instance"""
        if self.mock_mode:
            self.consumer = MockKafkaConsumer(
                topic="fetch-locations",
                consumer_group="location-worker",
                on_message=self._on_message
            )
        else:
            self.consumer = AIokafkaConsumer(
                topic="fetch-locations",
                consumer_group="location-worker",
                bootstrap_servers=self.bootstrap_servers,
                on_message=self._on_message
            )
    
    async def start(self) -> None:
        """Start consuming messages"""
        if not self.consumer:
            logger.error("consumer_not_initialized")
            return
        await self.consumer.start()
        logger.info("location_worker_started")
    
    async def stop(self) -> None:
        """Stop consumer"""
        if self.consumer:
            await self.consumer.stop()
        logger.info("location_worker_stopped")
    
    async def run(self) -> None:
        """Consume messages loop"""
        await self.start()
        await self.consumer.consume()
    
    async def _on_message(self, message: dict) -> None:
        """Process fetch-locations event."""
        try:
            job_id = message.get("job_id")
            account_id = message.get("account_id")
            access_token = message.get("access_token")

            def _extract_numeric_id(value) -> int | None:
                if value is None:
                    return None
                if isinstance(value, int):
                    return value
                s = str(value)
                if "/" in s:
                    s = s.split("/")[-1]
                try:
                    return int(s)
                except Exception:
                    return None

            account_id_int = _extract_numeric_id(account_id)
            
            logger.info("processing_fetch_locations", job_id=job_id, account_id=account_id)
            
            # Rate limiting
            if not await self.rate_limiter.acquire(tokens=1):
                logger.warning("rate_limit_exceeded", job_id=job_id)
                await self.retry_scheduler.schedule_retry(
                    message_id=account_id,
                    payload={**message, "type": "fetch_locations"},
                    error_code="429",
                    attempt=0
                )
                return
            
            # Fetch locations (mock or real, depending on MOCK_GOOGLE_API)
            locations = await google_api_client.get_locations(str(account_id), str(access_token))
            
            if not locations:
                logger.warning("no_locations_found", job_id=job_id, account_id=account_id)
                return
            
            # Publish fetch-reviews event for each location
            for location in locations:
                raw_location_name = location.get("name")
                # In real responses, location resource name is typically
                # "accounts/{account}/locations/{location}".
                derived_location_id = None
                if isinstance(raw_location_name, str) and "/locations/" in raw_location_name:
                    derived_location_id = raw_location_name.split("/locations/")[-1]

                location_id = (
                    location.get("location_id")
                    or location.get("id")
                    or derived_location_id
                )

                location_title = (
                    location.get("location_title")
                    or location.get("title")
                    or location.get("locationName")
                    or raw_location_name
                    or str(location_id)
                )

                google_account_id = location.get("google_account_id")
                if google_account_id is None and account_id_int is not None:
                    google_account_id = account_id_int

                success = await self.event_publisher.publish_fetch_reviews_event(
                    job_id=job_id,
                    account_id=account_id,
                    location_id=str(location_id),
                    location_name=str(location_title),
                    access_token=access_token,
                    record_id=location.get("id"),
                    client_id=location.get("client_id"),
                    google_account_id=google_account_id,
                    location_title=location.get("location_title"),
                    address=location.get("address"),
                    phone=location.get("phone"),
                    category=location.get("category"),
                    created_at=location.get("created_at"),
                    updated_at=location.get("updated_at"),
                )
                
                if not success:
                    logger.error(
                        "failed_to_publish_reviews_event",
                        job_id=job_id,
                        location_id=str(location_id),
                    )
            
            logger.info("locations_processed", job_id=job_id, account_id=account_id, count=len(locations))
        
        except Exception as e:
            logger.error("location_worker_error", job_id=message.get("job_id"), error=str(e))
            await self.event_publisher.publish_dlq_message(
                original_topic="fetch-locations",
                original_message=message,
                error=str(e),
                error_code="500"
            )
