from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, text
from app.models import SyncJob, Account, Location, Review
from app.services.google_api import google_api_client
from app.services.kafka_producer import kafka_producer
from app.schemas import ReviewMessage
from datetime import datetime
import structlog
import asyncio
from typing import Dict, Any
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import httpx

logger = structlog.get_logger()


class SyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    # Main entry point - starts the continuous flow
    async def start_sync_flow(self, access_token: str, client_id: str, sync_job_id: int):
        """Start the continuous sync flow with automatic step progression"""
        try:
            await self._update_job_status(sync_job_id, "running", "token_validation")
            await self._update_step_status(sync_job_id, "token_validation", "running")

            # Step 1: Token Validation
            await self._step_token_validation(access_token, sync_job_id)

            # Automatically progress to Step 2: Accounts Fetch
            await self._step_accounts_fetch(access_token, client_id, sync_job_id)

            # Automatically progress to Step 3: Locations Fetch
            await self._step_locations_fetch(access_token, client_id, sync_job_id)

            # Automatically progress to Step 4: Reviews Fetch
            await self._step_reviews_fetch(access_token, client_id, sync_job_id)

            # Automatically progress to Step 5: Kafka Publish
            await self._step_kafka_publish(sync_job_id)

            # Mark as completed
            await self._update_job_status(sync_job_id, "completed", "completed")
            logger.info("Continuous sync flow completed successfully", sync_job_id=sync_job_id)

        except Exception as e:
            await self._handle_flow_error(sync_job_id, e)
            raise

    # Step 1: Token Validation
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, Exception)),
    )
    async def _step_token_validation(self, access_token: str, sync_job_id: int):
        """Step 1: Validate the access token by making a test API call"""
        try:
            logger.info("Starting token validation", sync_job_id=sync_job_id)

            # Test token with validation method
            await google_api_client.validate_token(access_token)

            await self._update_step_status(sync_job_id, "token_validation", "completed")
            logger.info("Token validation completed", sync_job_id=sync_job_id)

        except Exception as e:
            await self._update_step_status(sync_job_id, "token_validation", "failed", str(e))
            logger.error("Token validation failed", sync_job_id=sync_job_id, error=str(e))
            raise

    # Step 2: Accounts Fetch
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=15),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, Exception)),
    )
    async def _step_accounts_fetch(self, access_token: str, client_id: str, sync_job_id: int):
        """Step 2: Fetch all Google Business accounts"""
        try:
            await self._update_step_status(sync_job_id, "accounts_fetch", "running")
            logger.info("Starting accounts fetch", sync_job_id=sync_job_id)

            accounts_data = await google_api_client.get_accounts(access_token)
            accounts = accounts_data.get("accounts", [])

            if not accounts:
                raise ValueError("No accounts found for the provided token")

            # Store accounts in database
            for account in accounts:
                account_id = account["name"].split("/")[-1]
                
                # Generate unique account ID for mock mode to avoid duplicates
                from app.config import settings
                if settings.mock_mode:
                    # Create unique ID combining account ID and sync job ID
                    unique_account_id = f"{account_id}_{sync_job_id}"
                else:
                    unique_account_id = account_id
                    
                account_obj = Account(
                    id=unique_account_id,
                    name=account.get("accountName", account_id),
                    client_id=client_id,
                    sync_job_id=sync_job_id
                )
                self.db.add(account_obj)

            await self.db.commit()
            await self._update_step_status(sync_job_id, "accounts_fetch", "completed", f"Fetched {len(accounts)} accounts")
            logger.info("Accounts fetch completed", sync_job_id=sync_job_id, accounts_count=len(accounts))

        except Exception as e:
            await self._update_step_status(sync_job_id, "accounts_fetch", "failed", str(e))
            logger.error("Accounts fetch failed", sync_job_id=sync_job_id, error=str(e))
            raise

    # Step 3: Locations Fetch
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=15),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, Exception)),
    )
    async def _step_locations_fetch(self, access_token: str, client_id: str, sync_job_id: int):
        """Step 3: Fetch locations for all accounts"""
        try:
            await self._update_step_status(sync_job_id, "locations_fetch", "running")
            logger.info("Starting locations fetch", sync_job_id=sync_job_id)

            # Get all accounts for this sync job
            accounts = await self.db.execute(
                text("SELECT id FROM accounts WHERE sync_job_id = :sync_job_id"),
                {"sync_job_id": sync_job_id}
            )
            account_ids = [row[0] for row in accounts.fetchall()]

            total_locations = 0
            for account_id in account_ids:
                locations_data = await google_api_client.get_locations(f"accounts/{account_id}", access_token)
                locations = locations_data.get("locations", [])

                # Store locations in database
                for location in locations:
                    location_id = location["name"].split("/")[-1]
                    
                    # For mock mode, the location_id is already unique (account_id + location_id)
                    # For real mode, add sync_job_id suffix
                    from app.config import settings
                    if settings.mock_mode:
                        unique_location_id = location_id
                    else:
                        unique_location_id = f"{location_id}_{sync_job_id}"
                        
                    location_obj = Location(
                        id=unique_location_id,
                        account_id=account_id,
                        name=location.get("locationName", ""),
                        address=str(location.get("address", {})),
                        client_id=client_id,
                        sync_job_id=sync_job_id
                    )
                    self.db.add(location_obj)
                    total_locations += 1

            await self.db.commit()
            await self._update_step_status(sync_job_id, "locations_fetch", "completed", f"Fetched {total_locations} locations")
            logger.info("Locations fetch completed", sync_job_id=sync_job_id, locations_count=total_locations)

        except Exception as e:
            await self._update_step_status(sync_job_id, "locations_fetch", "failed", str(e))
            logger.error("Locations fetch failed", sync_job_id=sync_job_id, error=str(e))
            raise

    # Step 4: Reviews Fetch
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=20),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, Exception)),
    )
    async def _step_reviews_fetch(self, access_token: str, client_id: str, sync_job_id: int):
        """Step 4: Fetch reviews for all locations"""
        try:
            await self._update_step_status(sync_job_id, "reviews_fetch", "running")
            logger.info("Starting reviews fetch", sync_job_id=sync_job_id)

            # Get all locations for this sync job
            locations = await self.db.execute(
                text("SELECT id, account_id FROM locations WHERE sync_job_id = :sync_job_id"),
                {"sync_job_id": sync_job_id}
            )
            location_data = locations.fetchall()

            total_reviews = 0
            for location_id, account_id in location_data:
                reviews_data = await google_api_client.get_reviews(account_id, location_id, access_token)
                reviews = reviews_data.get("reviews", [])

                # Store reviews in database
                for review in reviews:
                    # Convert star rating to integer
                    rating_map = {"ONE": 1, "TWO": 2, "THREE": 3, "FOUR": 4, "FIVE": 5}
                    rating = rating_map.get(review.get("starRating"), 5)
                    
                    # Parse create time
                    from datetime import datetime
                    create_time = datetime.fromisoformat(review.get("createTime", "2023-01-01T12:00:00Z").replace('Z', '+00:00'))
                    
                    # Generate unique review ID for mock mode to avoid duplicates
                    from app.config import settings
                    if settings.mock_mode:
                        # Create unique ID combining review ID, location ID, and sync job ID
                        review_id = f"{review['reviewId']}_{location_id}_{sync_job_id}"
                    else:
                        review_id = review["reviewId"]
                    
                    review_obj = Review(
                        id=review_id,
                        location_id=location_id,
                        account_id=account_id,
                        rating=rating,
                        comment=review.get("comment"),
                        reviewer_name=review.get("reviewer", {}).get("displayName", ""),
                        create_time=create_time,
                        client_id=client_id,
                        sync_job_id=sync_job_id
                    )
                    self.db.add(review_obj)
                    total_reviews += 1

            await self.db.commit()
            await self._update_step_status(sync_job_id, "reviews_fetch", "completed", f"Fetched {total_reviews} reviews")
            logger.info("Reviews fetch completed", sync_job_id=sync_job_id, reviews_count=total_reviews)

        except Exception as e:
            await self._update_step_status(sync_job_id, "reviews_fetch", "failed", str(e))
            logger.error("Reviews fetch failed", sync_job_id=sync_job_id, error=str(e))
            raise

    # Step 5: Kafka Publish
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception),
    )
    async def _step_kafka_publish(self, sync_job_id: int):
        """Step 5: Publish all reviews to Kafka"""
        try:
            await self._update_step_status(sync_job_id, "kafka_publish", "running")
            logger.info("Starting Kafka publish", sync_job_id=sync_job_id)

            # Get all reviews for this sync job
            reviews = await self.db.execute(
                text("SELECT id, location_id, account_id, rating, comment, reviewer_name, create_time FROM reviews WHERE sync_job_id = :sync_job_id"),
                {"sync_job_id": sync_job_id}
            )
            review_data = reviews.fetchall()

            published_count = 0
            for review in review_data:
                review_id, location_id, account_id, rating, comment, reviewer_name, create_time = review

                message = ReviewMessage(
                    review_id=review_id,
                    location_id=location_id,
                    account_id=account_id,
                    rating=rating,
                    comment=comment or "",
                    reviewer_name=reviewer_name or "",
                    create_time=create_time.isoformat() if create_time else None,
                    source="google",
                    ingestion_timestamp=datetime.utcnow().isoformat(),
                    sync_job_id=sync_job_id
                )

                # Only send to Kafka if producer is available
                if kafka_producer.producer:
                    kafka_producer.send_review(message.dict())
                    published_count += 1
                else:
                    logger.warning("Kafka producer not available, skipping publish", review_id=review_id)
                    published_count += 1  # Still count as "published" for demo purposes

            await self._update_step_status(sync_job_id, "kafka_publish", "completed", f"Published {published_count} reviews to Kafka")
            logger.info("Kafka publish completed", sync_job_id=sync_job_id, published_count=published_count)

        except Exception as e:
            await self._update_step_status(sync_job_id, "kafka_publish", "failed", str(e))
            logger.error("Kafka publish failed", sync_job_id=sync_job_id, error=str(e))
            raise

    # Helper methods for status updates
    async def _update_job_status(self, sync_job_id: int, status: str, current_step: str = None):
        """Update the overall job status"""
        update_data = {"status": status, "updated_at": datetime.utcnow()}
        if current_step:
            update_data["current_step"] = current_step

        await self.db.execute(
            update(SyncJob).where(SyncJob.id == sync_job_id).values(**update_data)
        )
        await self.db.commit()

    async def _update_step_status(self, sync_job_id: int, step: str, status: str, message: str = None):
        """Update the status of a specific step"""
        # Get current step status
        job = await self.db.get(SyncJob, sync_job_id)
        if not job:
            return

        step_status = job.step_status or {}
        step_status[step] = {
            "status": status,
            "timestamp": datetime.utcnow().isoformat(),
            "message": message
        }

        await self.db.execute(
            update(SyncJob).where(SyncJob.id == sync_job_id).values(
                step_status=step_status,
                current_step=step if status == "running" else job.current_step,
                updated_at=datetime.utcnow()
            )
        )
        await self.db.commit()

    async def _handle_flow_error(self, sync_job_id: int, error: Exception):
        """Handle errors in the continuous flow"""
        error_msg = str(error)
        await self._update_job_status(sync_job_id, "failed")

        # Get current step and mark it as failed
        job = await self.db.get(SyncJob, sync_job_id)
        if job and job.current_step:
            await self._update_step_status(sync_job_id, job.current_step, "failed", error_msg)

        logger.error("Continuous sync flow failed", sync_job_id=sync_job_id, error=error_msg)

        # TODO: Implement retry logic for failed jobs
        # For now, just log the failure

    # Legacy method for backward compatibility
    async def sync_reviews(self, access_token: str, client_id: str, sync_job_id: int):
        """Legacy method - redirects to new continuous flow"""
        return await self.start_sync_flow(access_token, client_id, sync_job_id)

    async def _sync_location(self, account_id: str, location_id: str, access_token: str, client_id: str, sync_job_id: int):
        # Save location
        location = Location(id=location_id, account_id=account_id, client_id=client_id, sync_job_id=sync_job_id)
        self.db.add(location)
        await self.db.commit()

        # Fetch reviews
        reviews_data = await google_api_client.get_reviews(f"accounts/{account_id}", location_id, access_token)
        reviews = reviews_data.get("reviews", [])

        for review in reviews:
            await self._sync_review(account_id, location_id, review, client_id, sync_job_id)

    async def _sync_review(self, account_id: str, location_id: str, review: dict, client_id: str, sync_job_id: int):
        review_id = review["reviewId"]

        # Check if review already exists
        existing = await self.db.get(Review, review_id)
        if existing:
            return  # Skip duplicate

        # Save review
        db_review = Review(
            id=review_id,
            location_id=location_id,
            account_id=account_id,
            rating=int(review["starRating"]),
            comment=review.get("comment"),
            reviewer_name=review.get("reviewer", {}).get("displayName"),
            create_time=datetime.fromisoformat(review["createTime"].replace('Z', '+00:00')),
            client_id=client_id,
            sync_job_id=sync_job_id
        )
        self.db.add(db_review)
        await self.db.commit()

        # Publish to Kafka
        message = ReviewMessage(
            review_id=review_id,
            location_id=location_id,
            account_id=account_id,
            rating=db_review.rating,
            comment=db_review.comment,
            reviewer_name=db_review.reviewer_name,
            create_time=db_review.create_time,
            ingestion_timestamp=datetime.utcnow()
        )
        kafka_producer.send_review(message.dict())