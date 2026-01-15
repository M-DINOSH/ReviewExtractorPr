"""Review Worker - Consumes fetch-reviews and publishes reviews-raw.

Uses GoogleAPIClient which supports both mock data (jsom/) and the real Google APIs.
"""

import asyncio
from typing import Optional, Set
from collections import defaultdict
import structlog

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler
from app.kafka_producer import KafkaEventPublisher
from app.services.google_api import google_api_client


_STAR_RATING_MAP: dict[str, int] = {
    "ONE": 1,
    "TWO": 2,
    "THREE": 3,
    "FOUR": 4,
    "FIVE": 5,
}


def _normalize_review_id(review: dict) -> str | None:
    rid = review.get("reviewId") or review.get("review_id") or review.get("id") or review.get("name")
    if rid is None:
        return None
    if isinstance(rid, str) and "/" in rid:
        return rid.split("/")[-1]
    return str(rid)


def _normalize_rating(review: dict) -> int | None:
    val = review.get("rating")
    if isinstance(val, int):
        return val
    if isinstance(val, str) and val.isdigit():
        return int(val)

    star = review.get("starRating") or review.get("star_rating")
    if isinstance(star, str):
        star = star.strip().upper()
        if star in _STAR_RATING_MAP:
            return _STAR_RATING_MAP[star]
    return None


def _normalize_reviewer_name(review: dict) -> str | None:
    direct = review.get("reviewer_name") or review.get("reviewerName")
    if direct:
        return str(direct)
    reviewer = review.get("reviewer")
    if isinstance(reviewer, dict):
        return reviewer.get("displayName") or reviewer.get("name")
    return None

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
        """Process fetch-reviews event."""
        try:
            job_id = message.get("job_id")
            location_id = message.get("location_id")
            account_id = message.get("account_id")
            access_token = message.get("access_token")
            
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
            
            # Fetch reviews (mock or real, depending on MOCK_GOOGLE_API)
            reviews = await google_api_client.get_reviews(str(account_id), str(location_id), str(access_token))
            
            if not reviews:
                logger.info("no_reviews_found", job_id=job_id, location_id=location_id)
                return
            
            review_count = 0
            duplicate_count = 0
            
            # Process each review
            for review in reviews:
                review_id = _normalize_review_id(review)
                if not review_id:
                    continue
                
                # Deduplication check
                if review_id in self.seen_reviews[job_id]:
                    duplicate_count += 1
                    continue
                
                self.seen_reviews[job_id].add(review_id)
                
                # Publish to reviews-raw topic
                rating = _normalize_rating(review)
                if rating is None:
                    # Default to 5 in mock-like cases where rating is missing
                    rating = 5

                text = review.get("comment") or review.get("text") or ""
                reviewer_name = _normalize_reviewer_name(review) or ""
                success = await self.event_publisher.publish_review_raw_event(
                    job_id=job_id,
                    review_id=review_id,
                    location_id=location_id,
                    account_id=account_id,
                    rating=rating,
                    text=str(text),
                    reviewer_name=str(reviewer_name),
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
