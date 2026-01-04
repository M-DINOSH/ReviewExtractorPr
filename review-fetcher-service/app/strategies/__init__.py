"""
Strategy pattern implementation for different sync strategies
"""

from typing import Dict, List, Any, Optional
from abc import ABC, abstractmethod
from enum import Enum

from ..core.interfaces import ISyncService
from ..core.services import logger
from .interfaces import IDataProvider


class SyncStrategy(Enum):
    """Available sync strategies"""
    SIMPLE = "simple"
    BATCH = "batch"
    STREAMING = "streaming"


class ISyncStrategy(ABC):
    """Strategy interface for sync operations"""

    @abstractmethod
    async def execute_sync(self, access_token: str, data_provider: IDataProvider) -> Dict[str, Any]:
        """Execute sync using specific strategy"""
        pass

    @abstractmethod
    def get_strategy_name(self) -> str:
        """Get strategy name"""
        pass


class SimpleSyncStrategy(ISyncStrategy):
    """Simple sync strategy - direct processing"""

    def get_strategy_name(self) -> str:
        return "simple"

    async def execute_sync(self, access_token: str, data_provider: IDataProvider) -> Dict[str, Any]:
        """Execute simple sync flow"""
        logger.info("Starting simple sync strategy", strategy=self.get_strategy_name())

        # Step 1: Get accounts
        accounts = await data_provider.get_accounts(access_token)

        if not accounts:
            logger.warning("No accounts found")
            return {
                "account": None,
                "locations": []
            }

        # Use first account for simplicity
        account = accounts[0]
        account_id = account.get("account_id") or account.get("id")

        # Step 2: Get locations
        locations = await data_provider.get_locations(account_id)

        # Step 3: Get reviews for each location
        locations_with_reviews = []
        for location in locations:
            location_id = location.get("location_id") or location.get("id")
            reviews = await data_provider.get_reviews(location_id)

            locations_with_reviews.append({
                "location": location,
                "reviews": reviews
            })

        result = {
            "account": account,
            "locations": locations_with_reviews
        }

        logger.info("Simple sync strategy completed",
                   strategy=self.get_strategy_name(),
                   account_id=account_id,
                   locations_count=len(locations))

        return result


class BatchSyncStrategy(ISyncStrategy):
    """Batch sync strategy - processes locations in batches"""

    def __init__(self, batch_size: int = 10):
        self.batch_size = batch_size

    def get_strategy_name(self) -> str:
        return "batch"

    async def execute_sync(self, access_token: str, data_provider: IDataProvider) -> Dict[str, Any]:
        """Execute batch sync flow"""
        logger.info("Starting batch sync strategy",
                   strategy=self.get_strategy_name(),
                   batch_size=self.batch_size)

        # Step 1: Get accounts
        accounts = await data_provider.get_accounts(access_token)

        if not accounts:
            logger.warning("No accounts found")
            return {
                "account": None,
                "locations": []
            }

        # Use first account
        account = accounts[0]
        account_id = account.get("account_id") or account.get("id")

        # Step 2: Get locations
        locations = await data_provider.get_locations(account_id)

        # Step 3: Process locations in batches
        locations_with_reviews = []
        for i in range(0, len(locations), self.batch_size):
            batch = locations[i:i + self.batch_size]
            batch_tasks = []

            # Create tasks for batch processing
            for location in batch:
                location_id = location.get("location_id") or location.get("id")
                task = self._process_location(location, location_id, data_provider)
                batch_tasks.append(task)

            # Execute batch
            batch_results = await asyncio.gather(*batch_tasks, return_exceptions=True)

            # Process results
            for location, result in zip(batch, batch_results):
                if isinstance(result, Exception):
                    logger.error("Failed to process location",
                               location_id=location.get("id"),
                               error=str(result))
                    reviews = []
                else:
                    reviews = result

                locations_with_reviews.append({
                    "location": location,
                    "reviews": reviews
                })

        result = {
            "account": account,
            "locations": locations_with_reviews
        }

        logger.info("Batch sync strategy completed",
                   strategy=self.get_strategy_name(),
                   account_id=account_id,
                   locations_count=len(locations),
                   batches=len(list(range(0, len(locations), self.batch_size))))

        return result

    async def _process_location(self, location: Dict[str, Any], location_id: str, data_provider: IDataProvider) -> List[Dict[str, Any]]:
        """Process a single location"""
        return await data_provider.get_reviews(location_id)


class StreamingSyncStrategy(ISyncStrategy):
    """Streaming sync strategy - processes one location at a time"""

    def get_strategy_name(self) -> str:
        return "streaming"

    async def execute_sync(self, access_token: str, data_provider: IDataProvider) -> Dict[str, Any]:
        """Execute streaming sync flow"""
        logger.info("Starting streaming sync strategy", strategy=self.get_strategy_name())

        # Step 1: Get accounts
        accounts = await data_provider.get_accounts(access_token)

        if not accounts:
            logger.warning("No accounts found")
            return {
                "account": None,
                "locations": []
            }

        # Use first account
        account = accounts[0]
        account_id = account.get("account_id") or account.get("id")

        # Step 2: Get locations
        locations = await data_provider.get_locations(account_id)

        # Step 3: Process locations sequentially
        locations_with_reviews = []
        for location in locations:
            location_id = location.get("location_id") or location.get("id")
            reviews = await data_provider.get_reviews(location_id)

            locations_with_reviews.append({
                "location": location,
                "reviews": reviews
            })

            # Small delay to prevent overwhelming the API
            await asyncio.sleep(0.01)

        result = {
            "account": account,
            "locations": locations_with_reviews
        }

        logger.info("Streaming sync strategy completed",
                   strategy=self.get_strategy_name(),
                   account_id=account_id,
                   locations_count=len(locations))

        return result


class SyncStrategyFactory:
    """Factory for creating sync strategies"""

    @staticmethod
    def create_strategy(strategy: SyncStrategy, **kwargs) -> ISyncStrategy:
        """Create a sync strategy instance"""
        if strategy == SyncStrategy.SIMPLE:
            return SimpleSyncStrategy()
        elif strategy == SyncStrategy.BATCH:
            batch_size = kwargs.get('batch_size', 10)
            return BatchSyncStrategy(batch_size=batch_size)
        elif strategy == SyncStrategy.STREAMING:
            return StreamingSyncStrategy()
        else:
            raise ValueError(f"Unknown sync strategy: {strategy}")</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/review-fetcher-service/app/strategies/__init__.py