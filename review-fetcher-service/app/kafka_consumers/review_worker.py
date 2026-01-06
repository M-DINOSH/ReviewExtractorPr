"""
Review Worker - consumes fetch-reviews events and fetches reviews with deduplication
Implements Single Responsibility Principle (SRP)
"""

import asyncio
import logging
import random
from typing import Optional, Set
from collections import defaultdict

from app.kafka_consumers.base import AIokafkaConsumer, MockKafkaConsumer
from app.rate_limiter import TokenBucketLimiter
from app.retry import RetryScheduler
from app.kafka_producer import KafkaEventPublisher

logger = logging.getLogger(__name__)


class ReviewWorker:
    """
    Consumes fetch-reviews events
    Simulates paginated Google API calls to fetch reviews
    Deduplicates review IDs (using set for O(1) lookup)
    Publishes to reviews-raw topic
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
        """
        Process fetch-reviews event
        Uses sliding window pagination to fetch reviews
        
        Message format:
        {
            "type": "fetch_reviews",
            "job_id": str,
            "account_id": str,
            "location_id": str,
            "location_name": str,
            "timestamp": str
        }
        """
        try:
            job_id = message.get("job_id")
            location_id = message.get("location_id")
            account_id = message.get("account_id")
            location_name = message.get("location_name")
            
            logger.info(
                "processing_fetch_reviews",
                job_id=job_id,
                location_id=location_id
            )
            
            # Rate limiting
            if not await self.rate_limiter.acquire(tokens=1):
                logger.warning(
                    "rate_limit_exceeded",
                    job_id=job_id
                )
                await self.retry_scheduler.schedule_retry(
                    message_id=location_id,
                    payload=message,
                    error_code="429",
                    attempt=0
                )
                return
            
            # Fetch reviews with pagination
            review_count = 0
            duplicate_count = 0
            
            # Sliding window pagination: fetch reviews page by page
            page_size = 20
            page = 0
            
            while True:
                reviews = await self._fetch_reviews_from_google(
                    location_id,
                    job_id,
                    page=page,
                    page_size=page_size
                )
                
                if not reviews:
                    break  # No more pages
                
                for review in reviews:
                    review_id = review["id"]
                    
                    # Deduplication check (set for O(1) lookup)
                    if review_id in self.seen_reviews[job_id]:
                        duplicate_count += 1
                        logger.debug(
                            "duplicate_review_skipped",
                            review_id=review_id
                        )
                        continue
                    
                    # Mark as seen
                    self.seen_reviews[job_id].add(review_id)
                    
                    # Publish to reviews-raw topic
                    success = await self.event_publisher.publish_review_raw_event(
                        job_id=job_id,
                        review_id=review_id,
                        location_id=location_id,
                        account_id=account_id,
                        rating=review["rating"],
                        text=review["text"],
                        reviewer_name=review["reviewer_name"]
                    )
                    
                    if success:
                        review_count += 1
                    else:
                        logger.error(
                            "failed_to_publish_review",
                            review_id=review_id
                        )
                
                page += 1
            
            logger.info(
                "reviews_processed",
                job_id=job_id,
                location_id=location_id,
                review_count=review_count,
                duplicates_skipped=duplicate_count
            )
        
        except Exception as e:
            logger.error(
                f"review_worker_error",
                job_id=message.get("job_id"),
                error=str(e)
            )
            await self.event_publisher.publish_dlq_message(
                original_topic="fetch-reviews",
                original_message=message,
                error=str(e),
                error_code="500"
            )
    
    async def _fetch_reviews_from_google(
        self,
        location_id: str,
        job_id: str,
        page: int = 0,
        page_size: int = 20
    ) -> list[dict]:
        """
        Simulate paginated Google API call for reviews
        
        Sliding window pattern:
        - Each page fetches page_size items
        - page * page_size = start offset
        - Implementation detail: in production use cursor-based pagination
        """
        # Simulate API latency
        await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Simulate occasional failures (3% chance)
        if random.random() < 0.03:
            raise Exception("Simulated Google API error")
        
        # Return mock reviews (fewer reviews on last page)
        total_reviews = random.randint(5, 50)
        start_idx = page * page_size
        
        if start_idx >= total_reviews:
            return []  # No more pages
        
        end_idx = min(start_idx + page_size, total_reviews)
        
        reviews = []
        for i in range(start_idx, end_idx):
            reviews.append({
                "id": f"review_{location_id}_{i}",
                "rating": random.randint(1, 5),
                "text": f"Review {i} for {location_id}: Great service!",
                "reviewer_name": f"Customer_{i}"
            })
        
        return reviews
    
    def get_deduplication_stats(self, job_id: str) -> dict:
        """Get deduplication statistics for a job"""
        return {
            "job_id": job_id,
            "total_unique_reviews": len(self.seen_reviews[job_id])
        }
    
    def clear_job_cache(self, job_id: str) -> None:
        """Clear deduplication cache for completed job"""
        if job_id in self.seen_reviews:
            del self.seen_reviews[job_id]
            logger.info("cleared_job_cache job_id=%s", job_id)
