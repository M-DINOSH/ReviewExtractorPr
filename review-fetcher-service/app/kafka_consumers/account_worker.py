"""
Account Worker - Consumes fetch-accounts events and fetches accounts from mock data
"""

import asyncio
from typing import Callable, Optional
import structlog

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler, ExponentialBackoffPolicy
from app.kafka_producer import KafkaEventPublisher
from app.services.mock_data import mock_data_service

logger = structlog.get_logger()


class AccountWorker:
    """Consumes fetch-accounts events and publishes fetch-locations events"""
    
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
        """Process fetch-accounts event - fetch accounts from mock data"""
        try:
            job_id = message.get("job_id")
            
            logger.info("processing_fetch_accounts", job_id=job_id)
            
            # Rate limiting
            if not await self.rate_limiter.acquire(tokens=1):
                logger.warning("rate_limit_exceeded", job_id=job_id)
                await self.retry_scheduler.schedule_retry(
                    message_id=job_id,
                    payload={**message, "type": "fetch_accounts"},
                    error_code="429",
                    attempt=0
                )
                return
            
            # Fetch accounts from mock data
            accounts = await mock_data_service.get_accounts()
            
            if not accounts:
                logger.warning("no_accounts_found", job_id=job_id)
                return
            
            # Publish fetch-locations event for each account
            for account in accounts:
                account_id = account.get("account_id", account.get("id"))
                success = await self.event_publisher.publish_fetch_locations_event(
                    job_id=job_id,
                    account_id=account_id,
                    account_name=account["display_name"],
                    access_token=message.get("access_token"),
                    google_account_name=account.get("google_account_name") or account.get("name"),
                    account_display_name=account.get("account_display_name") or account.get("display_name"),
                    client_id=account.get("client_id"),
                    created_at=account.get("created_at"),
                    updated_at=account.get("updated_at"),
                    record_id=account.get("id"),
                )
                
                if not success:
                    logger.error(
                        "failed_to_publish_location_event",
                        job_id=job_id,
                        account_id=account["id"]
                    )
            
            logger.info("accounts_processed", job_id=job_id, count=len(accounts))
        
        except Exception as e:
            logger.error("account_worker_error", job_id=message.get("job_id"), error=str(e))
            await self.event_publisher.publish_dlq_message(
                original_topic="fetch-accounts",
                original_message=message,
                error=str(e),
                error_code="500"
            )
