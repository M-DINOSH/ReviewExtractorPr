"""
Simplified Sync Service for Direct JSON Response

This service provides a simplified flow that returns combined JSON data
directly without database persistence or Kafka messaging.
Used for both Google and Mock modes with identical behavior.
"""

import structlog
from typing import Dict, List, Any, Optional
from app.services.data_providers import get_data_provider, DataProvider
from app.config import settings
from app.strategies import ISyncStrategy, SyncStrategy, SyncStrategyFactory

logger = structlog.get_logger()


class SimpleSyncService:
    """Service for simplified sync flow with strategy pattern support"""

    def __init__(self, data_mode: str = None, strategy: Optional[ISyncStrategy] = None):
        if data_mode is None:
            data_mode = settings.data_mode
        self.data_provider: DataProvider = get_data_provider(
            data_mode,
            google_api_client=None  # Will be set if needed for Google mode
        )

        # Strategy pattern for different sync approaches
        self.strategy = strategy or SyncStrategyFactory.create_strategy(SyncStrategy.SIMPLE)

    async def sync_reviews(self, access_token: str) -> Dict[str, Any]:
        """
        Execute the complete sync flow using the configured strategy

        Args:
            access_token: OAuth access token (used for account discovery in Google mode)

        Returns:
            Dict containing account, locations, and reviews data
        """
        logger.info("Starting sync with strategy",
                   strategy=self.strategy.get_strategy_name(),
                   data_mode=settings.data_mode)

        # Use strategy pattern to execute sync
        result = await self.strategy.execute_sync(access_token, self.data_provider)

        logger.info("Sync completed with strategy",
                   strategy=self.strategy.get_strategy_name(),
                   account_id=result.get("account", {}).get("id"),
                   locations_count=len(result.get("locations", [])))

        return result