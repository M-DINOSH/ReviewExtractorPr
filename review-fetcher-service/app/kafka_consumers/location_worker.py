"""
Location Worker - consumes fetch-locations events and fetches locations
Implements Single Responsibility Principle (SRP)
"""

import asyncio
import logging
import random
from typing import Optional

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler
from app.kafka_producer import KafkaEventPublisher

logger = logging.getLogger(__name__)


class LocationWorker:
    """
    Consumes fetch-locations events
    Simulates Google API call to list locations for an account
    Publishes fetch-reviews events
    """
    
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
        """
        Process fetch-locations event
        
        Message format:
        {
            "type": "fetch_locations",
            "job_id": str,
            "account_id": str,
            "account_name": str,
            "timestamp": str
        }
        """
        try:
            job_id = message.get("job_id")
            account_id = message.get("account_id")
            account_name = message.get("account_name")
            
            logger.info(
                "processing_fetch_locations",
                job_id=job_id,
                account_id=account_id
            )
            
            # Rate limiting
            if not await self.rate_limiter.acquire(tokens=1):
                logger.warning(
                    "rate_limit_exceeded",
                    job_id=job_id
                )
                await self.retry_scheduler.schedule_retry(
                    message_id=account_id,
                    payload=message,
                    error_code="429",
                    attempt=0
                )
                return
            
            # Simulate Google API call
            locations = await self._fetch_locations_from_google(
                account_id,
                job_id
            )
            
            if not locations:
                raise Exception("No locations found")
            
            # Publish fetch-reviews events for each location
            for location in locations:
                success = await self.event_publisher.publish_fetch_reviews_event(
                    job_id=job_id,
                    account_id=account_id,
                    location_id=location["id"],
                    location_name=location["name"]
                )
                
                if not success:
                    logger.error(
                        "failed_to_publish_reviews_event",
                        job_id=job_id,
                        location_id=location["id"]
                    )
            
            logger.info(
                "locations_processed",
                job_id=job_id,
                account_id=account_id,
                location_count=len(locations)
            )
        
        except Exception as e:
            logger.error(
                f"location_worker_error",
                job_id=message.get("job_id"),
                error=str(e)
            )
            await self.event_publisher.publish_dlq_message(
                original_topic="fetch-locations",
                original_message=message,
                error=str(e),
                error_code="500"
            )
    
    async def _fetch_locations_from_google(
        self,
        account_id: str,
        job_id: str
    ) -> list[dict]:
        """
        Simulate Google Business Profile API call for locations
        """
        # Simulate API latency
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Simulate occasional failures (5% chance)
        if random.random() < 0.05:
            raise Exception("Simulated Google API error")
        
        # Return mock locations
        return [
            {
                "id": f"location_{account_id}_1",
                "name": f"Branch 1 - {account_id}"
            },
            {
                "id": f"location_{account_id}_2",
                "name": f"Branch 2 - {account_id}"
            }
        ]
