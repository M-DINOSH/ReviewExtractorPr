"""Account Worker - Consumes fetch-accounts and publishes fetch-locations.

Uses GoogleAPIClient which supports both mock data (jsom/) and the real Google APIs.
"""

import asyncio
from typing import Callable, Optional
import structlog

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler, ExponentialBackoffPolicy
from app.kafka_producer import KafkaEventPublisher
from app.services.google_api import google_api_client

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
        """Process fetch-accounts event."""
        try:
            job_id = message.get("job_id")
            access_token = message.get("access_token")
            
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
            
            # Fetch accounts (mock or real, depending on MOCK_GOOGLE_API)
            accounts = await google_api_client.get_accounts(access_token)
            
            if not accounts:
                logger.warning("no_accounts_found", job_id=job_id)
                return
            
            # Publish fetch-locations event for each account
            def _extract_numeric_id(value) -> str | None:
                if value is None:
                    return None
                if isinstance(value, int):
                    return str(value)
                s = str(value)
                if "/" in s:
                    s = s.split("/")[-1]
                return s if s.isdigit() else None

            for account in accounts:
                raw_account_name = account.get("name") or account.get("google_account_name")

                # Pipeline account_id should be a numeric ID string when possible.
                # - Mock mode locations join on locations.google_account_id (numeric)
                # - Real mode API calls accept either numeric id or "accounts/{id}"
                pipeline_account_id = (
                    _extract_numeric_id(account.get("account_id"))
                    or _extract_numeric_id(account.get("id"))
                    or _extract_numeric_id(raw_account_name)
                    or (str(account.get("account_id") or account.get("id") or raw_account_name) if raw_account_name else None)
                )
                if pipeline_account_id is None:
                    continue

                account_display = (
                    account.get("display_name")
                    or account.get("account_display_name")
                    or account.get("accountName")
                    or raw_account_name
                    or str(pipeline_account_id)
                )

                success = await self.event_publisher.publish_fetch_locations_event(
                    job_id=job_id,
                    account_id=pipeline_account_id,
                    account_name=str(account_display),
                    access_token=access_token,
                    google_account_name=account.get("google_account_name") or raw_account_name,
                    account_display_name=account.get("account_display_name") or account.get("display_name") or account.get("accountName"),
                    client_id=account.get("client_id"),
                    created_at=account.get("created_at"),
                    updated_at=account.get("updated_at"),
                    record_id=account.get("id"),
                )
                
                if not success:
                    logger.error(
                        "failed_to_publish_location_event",
                        job_id=job_id,
                        account_id=pipeline_account_id,
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
