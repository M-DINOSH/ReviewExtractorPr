"""
Simplified Sync Service for Direct JSON Response

This service provides a simplified flow that returns combined JSON data
directly without database persistence or Kafka messaging.
Used for both Google and Mock modes with identical behavior.
"""

import structlog
from typing import Dict, List, Any
from app.services.data_providers import get_data_provider, DataProvider
from app.config import settings

logger = structlog.get_logger()


class SimpleSyncService:
    """Service for simplified sync flow returning combined JSON"""

    def __init__(self, data_mode: str = None):
        if data_mode is None:
            data_mode = settings.data_mode
        self.data_provider: DataProvider = get_data_provider(
            data_mode,
            google_api_client=None  # Will be set if needed for Google mode
        )

    async def sync_reviews(self, access_token: str) -> Dict[str, Any]:
        """
        Execute the complete sync flow and return combined JSON

        Args:
            access_token: OAuth access token (used for account discovery in Google mode)

        Returns:
            Dict containing account, locations, and reviews data
        """
        try:
            logger.info("Starting simplified sync flow", data_mode=settings.data_mode)

            # Step 1: Get accounts
            accounts = await self.data_provider.get_accounts(access_token)

            if not accounts:
                logger.warning("No accounts found")
                return {
                    "account": None,
                    "locations": []
                }

            # In both modes, we work with the first account
            account = accounts[0]
            account_id = str(account.get("account_id"))

            logger.info("Processing account",
                       account_id=account_id,
                       account_name=account.get("account_display_name"))

            # Step 2: Get all locations for this account
            locations_data = await self.data_provider.get_locations(account_id)

            # Step 3: For each location, get reviews
            locations_with_reviews = []
            for location in locations_data:
                location_id = str(location.get("location_id"))

                # Get reviews for this location
                reviews = await self.data_provider.get_reviews(location_id)

                # Add reviews to location data
                location_with_reviews = {
                    "location": location,
                    "reviews": reviews
                }
                locations_with_reviews.append(location_with_reviews)

            # Combine into final response
            result = {
                "account": account,
                "locations": locations_with_reviews
            }

            logger.info("Simplified sync flow completed",
                       account_id=account_id,
                       locations_count=len(locations_with_reviews),
                       total_reviews=sum(len(loc.get("reviews", [])) for loc in locations_with_reviews))

            return result

        except Exception as e:
            logger.error("Simplified sync flow failed", error=str(e))
            raise