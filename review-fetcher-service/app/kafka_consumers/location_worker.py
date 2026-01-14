"""
Location Worker - Consumes fetch-locations events and fetches locations from mock data
"""

import asyncio
from typing import Optional
import structlog

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler
from app.kafka_producer import KafkaEventPublisher
from app.services.mock_data import mock_data_service

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
        """Process fetch-locations event - fetch locations from mock data"""
        try:
            job_id = message.get("job_id")
            account_id = message.get("account_id")
            
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
            
            # Fetch locations from mock data
            locations = await mock_data_service.get_locations(account_id)
            
            if not locations:
                logger.warning("no_locations_found", job_id=job_id, account_id=account_id)
                return
            
            # Publish fetch-reviews event for each location
            for location in locations:
                success = await self.event_publisher.publish_fetch_reviews_event(
                    job_id=job_id,
                    account_id=account_id,
                    location_id=location["location_id"],
                    location_name=location["location_title"],
                    access_token=message.get("access_token")
                )
                
                if not success:
                    logger.error(
                        "failed_to_publish_reviews_event",
                        job_id=job_id,
                        location_id=location["location_id"]
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
