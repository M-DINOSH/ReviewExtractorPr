"""
Simplified Sync Service for Google Business Profile API

Production-ready service for fetching Google Business Profile reviews.
"""

import structlog
from typing import Dict, List, Any, Optional
from app.services.data_providers import get_data_provider
from app.services.google_api import google_api_client
from app.strategies import ISyncStrategy, SyncStrategy, SyncStrategyFactory

logger = structlog.get_logger()


class SimpleSyncService:
    """Service for simplified sync flow with Google Business Profile API"""

    def __init__(self, strategy: Optional[ISyncStrategy] = None):
        # Always use Google API client for production
        self.data_provider = get_data_provider(google_api_client)

        # Strategy pattern for different sync approaches
        self.strategy = strategy or SyncStrategyFactory.create_strategy(SyncStrategy.SIMPLE)

    async def sync_reviews(self, access_token: str) -> Dict[str, Any]:
        """
        Execute the complete sync flow using Google Business Profile API

        Args:
            access_token: OAuth access token for Google API authentication

        Returns:
            Dict containing account, locations, and reviews data
        """
        logger.info("Starting Google API sync",
                   strategy=self.strategy.get_strategy_name())

        # Use strategy pattern to execute sync
        result = await self.strategy.execute_sync(access_token, self.data_provider)

        logger.info("Google API sync completed",
                   strategy=self.strategy.get_strategy_name(),
                   account_id=result.get("account", {}).get("id"),
                   locations_count=len(result.get("locations", [])))

        return result