from sqlalchemy.ext.asyncio import AsyncSession
from app.models import SyncJob, Account, Location, Review
from app.services.google_api import google_api_client
from app.services.kafka_producer import kafka_producer
from app.schemas import ReviewMessage
from datetime import datetime
import structlog

logger = structlog.get_logger()


class SyncService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def sync_reviews(self, access_token: str, client_id: str, sync_job_id: int):
        try:
            # Update job status
            await self._update_job_status(sync_job_id, "running")

            # Fetch accounts
            accounts_data = await google_api_client.get_accounts(access_token)
            accounts = accounts_data.get("accounts", [])

            for account in accounts:
                account_id = account["name"].split("/")[-1]
                await self._sync_account(account_id, access_token, client_id, sync_job_id)

            await self._update_job_status(sync_job_id, "completed")
            logger.info("Sync completed", sync_job_id=sync_job_id)

        except Exception as e:
            await self._update_job_status(sync_job_id, "failed")
            logger.error("Sync failed", sync_job_id=sync_job_id, error=str(e))
            raise

    async def _sync_account(self, account_id: str, access_token: str, client_id: str, sync_job_id: int):
        # Save account
        account = Account(id=account_id, name=account_id, client_id=client_id, sync_job_id=sync_job_id)
        self.db.add(account)
        await self.db.commit()

        # Fetch locations
        locations_data = await google_api_client.get_locations(f"accounts/{account_id}", access_token)
        locations = locations_data.get("locations", [])

        for location in locations:
            location_id = location["name"].split("/")[-1]
            await self._sync_location(account_id, location_id, access_token, client_id, sync_job_id)

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

    async def _update_job_status(self, job_id: int, status: str):
        job = await self.db.get(SyncJob, job_id)
        if job:
            job.status = status
            await self.db.commit()