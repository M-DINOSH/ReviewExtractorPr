"""
Review Worker - Consumes fetch-reviews events and publishes reviews from mock data
"""

import asyncio
from typing import Optional, Set
from collections import defaultdict
import structlog

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler
from app.kafka_producer import KafkaEventPublisher
from app.services.mock_data import mock_data_service

logger = structlog.get_logger()


class ReviewWorker:
    """Consumes fetch-reviews events and publishes reviews from mock data"""
    
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
        
        # Deduplication: track seen review IDs per job
        self.seen_reviews: dict[str, Set[str]] = defaultdict(set)
        
        self.consumer = None
        self._setup_consumer()
    
    def _setup_consumer(self) -> None:
        """Create consumer instance"""
        if self.mock_mode:
            self.consumer = MockKafkaConsumer(
                topic="fetch-reviews",
                consumer_group="review-worker",
                on_message=self._on_message
            )
        else:
            self.consumer = AIokafkaConsumer(
                topic="fetch-reviews",
                consumer_group="review-worker",
                bootstrap_servers=self.bootstrap_servers,
                on_message=self._on_message
            )
    
    async def start(self) -> None:
        """Start consuming messages"""
        if not self.consumer:
            logger.error("consumer_not_initialized")
            return
        await self.consumer.start()
        logger.info("review_worker_started")
    
    async def stop(self) -> None:
        """Stop consumer"""
        if self.consumer:
            await self.consumer.stop()
        logger.info("review_worker_stopped")
    
    async def run(self) -> None:
        """Consume messages loop"""
        await self.start()
        await self.consumer.consume()
    
    async def _on_message(self, message: dict) -> None:
        """Process fetch-reviews event - fetch reviews from mock data"""
        try:
            job_id = message.get("job_id")
            location_id = message.get("location_id")
            
            logger.info("processing_fetch_reviews", job_id=job_id, location_id=location_id)
            
            # Rate limiting
            if not await self.rate_limiter.acquire(tokens=1):
                logger.warning("rate_limit_exceeded", job_id=job_id)
                await self.retry_scheduler.schedule_retry(
                    message_id=location_id,
                    payload={**message, "type": "fetch_reviews"},
                    error_code="429",
                    attempt=0
                )
                return
            
            # Fetch reviews from mock data
            reviews = await mock_data_service.get_reviews(location_id)
            
            if not reviews:
                logger.info("no_reviews_found", job_id=job_id, location_id=location_id)
                return
            
            review_count = 0
            duplicate_count = 0
            
            # Process each review
            for review in reviews:
                review_id = review.get("id")
                
                # Deduplication check
                if review_id in self.seen_reviews[job_id]:
                    duplicate_count += 1
                    continue
                
                self.seen_reviews[job_id].add(review_id)
                
                # Publish to reviews-raw topic
                success = await self.event_publisher.publish_review_raw_event(
                    job_id=job_id,
                    review_id=review_id,
                    location_id=location_id,
                    account_id=message.get("account_id"),
                    rating=review.get("rating"),
                    text=review.get("comment"),
                    reviewer_name=review.get("reviewer_name"),
                    record_id=review.get("id"),
                    client_id=review.get("client_id"),
                    google_review_id=review.get("google_review_id"),
                    comment=review.get("comment"),
                    reviewer_photo_url=review.get("reviewer_photo_url"),
                    review_created_time=review.get("review_created_time"),
                    reply_text=review.get("reply_text"),
                    reply_time=review.get("reply_time"),
                    created_at=review.get("created_at"),
                    updated_at=review.get("updated_at"),
                )
                
                if success:
                    review_count += 1
            
            logger.info("reviews_processed", job_id=job_id, location_id=location_id, count=review_count)
        
        except Exception as e:
            logger.error("review_worker_error", job_id=message.get("job_id"), error=str(e))
            await self.event_publisher.publish_dlq_message(
                original_topic="fetch-reviews",
                original_message=message,
                error=str(e),
                error_code="500"
            )
