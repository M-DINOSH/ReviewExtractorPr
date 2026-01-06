"""
Account Worker - consumes fetch-accounts events and fetches Google accounts
Implements Single Responsibility Principle (SRP)
"""

import asyncio
import logging
import random
from typing import Callable, Optional
from datetime import datetime

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler, ExponentialBackoffPolicy
from app.kafka_producer import KafkaEventPublisher

logger = logging.getLogger(__name__)


class AccountWorker:
    """
    Consumes fetch-accounts events
    Simulates Google API call to list accounts
    Publishes fetch-locations events
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
                topic="fetch-accounts",
                consumer_group="account-worker",
                on_message=self._on_message
            )
        else:
            self.consumer = AIokafkaConsumer(
                topic="fetch-accounts",
                consumer_group="account-worker",
                bootstrap_servers=self.bootstrap_servers,
                on_message=self._on_message
            )
    
    async def start(self) -> None:
        """Start consuming messages"""
        if not self.consumer:
            logger.error("consumer_not_initialized")
            return
        
        await self.consumer.start()
        logger.info("account_worker_started")
    
    async def stop(self) -> None:
        """Stop consumer"""
        if self.consumer:
            await self.consumer.stop()
        logger.info("account_worker_stopped")
    
    async def run(self) -> None:
        """Consume messages loop"""
        await self.start()
        await self.consumer.consume()
    
    async def _on_message(self, message: dict) -> None:
        """
        Process fetch-accounts event
        
        Message format:
        {
            "type": "fetch_accounts",
            "job_id": str,
            "access_token": str,
            "timestamp": str
        }
        """
        try:
            job_id = message.get("job_id")
            access_token = message.get("access_token")
            
            logger.info(
                "processing_fetch_accounts",
                job_id=job_id
            )
            
            # Rate limiting
            if not await self.rate_limiter.acquire(tokens=1):
                logger.warning(
                    "rate_limit_exceeded",
                    job_id=job_id
                )
                # Schedule for retry with backoff
                await self.retry_scheduler.schedule_retry(
                    message_id=job_id,
                    payload=message,
                    error_code="429",
                    attempt=0
                )
                return
            
            # Simulate Google API call
            accounts = await self._fetch_accounts_from_google(
                access_token,
                job_id
            )
            
            if not accounts:
                raise Exception("No accounts found")
            
            # Publish fetch-locations events for each account
            for account in accounts:
                success = await self.event_publisher.publish_fetch_locations_event(
                    job_id=job_id,
                    account_id=account["id"],
                    account_name=account["name"]
                )
                
                if not success:
                    logger.error(
                        "failed_to_publish_location_event",
                        job_id=job_id,
                        account_id=account["id"]
                    )
            
            logger.info(
                "accounts_processed",
                job_id=job_id,
                account_count=len(accounts)
            )
        
        except Exception as e:
            logger.error(
                f"account_worker_error",
                job_id=message.get("job_id"),
                error=str(e)
            )
            # Send to DLQ
            await self.event_publisher.publish_dlq_message(
                original_topic="fetch-accounts",
                original_message=message,
                error=str(e),
                error_code="500"
            )
    
    async def _fetch_accounts_from_google(
        self,
        access_token: str,
        job_id: str
    ) -> list[dict]:
        """
        Simulate Google Business Profile API call
        In production: use httpx to call real API
        """
        # Simulate API latency
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Simulate occasional failures (5% chance)
        if random.random() < 0.05:
            raise Exception("Simulated Google API error")
        
        # Return mock accounts
        return [
            {
                "id": f"account_{job_id}_1",
                "name": f"Business Account 1 for job {job_id}"
            },
            {
                "id": f"account_{job_id}_2",
                "name": f"Business Account 2 for job {job_id}"
            }
        ]
