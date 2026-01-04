"""
Google Business Profile API Data Provider

Production-ready data provider for Google Business Profile API.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any
import structlog

logger = structlog.get_logger()


class DataProvider(ABC):
    """Abstract base class for data providers"""

    @abstractmethod
    async def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Get all accounts accessible with the access token"""
        pass

    @abstractmethod
    async def get_locations(self, account_id: str) -> List[Dict[str, Any]]:
        """Get all locations for a specific account"""
        pass

    @abstractmethod
    async def get_reviews(self, location_id: str) -> List[Dict[str, Any]]:
        """Get all reviews for a specific location"""
        pass


class GoogleDataProvider(DataProvider):
    """Google Business Profile API data provider"""

    def __init__(self, google_api_client):
        self.google_api_client = google_api_client

    async def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Get accounts from Google Business Profile API"""
        return await self.google_api_client.get_accounts(access_token)

    async def get_locations(self, account_id: str) -> List[Dict[str, Any]]:
        """Get locations for account from Google Business Profile API"""
        return await self.google_api_client.get_locations(account_id)

    async def get_reviews(self, location_id: str) -> List[Dict[str, Any]]:
        """Get reviews for location from Google Business Profile API"""
        return await self.google_api_client.get_reviews(location_id)


def get_data_provider(google_api_client) -> DataProvider:
    """
    Factory function to get the Google data provider

    Args:
        google_api_client: Google API client instance

    Returns:
        GoogleDataProvider instance
    """
    return GoogleDataProvider(google_api_client)