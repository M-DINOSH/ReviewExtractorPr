"""
Data Provider Interface and Implementations

This module provides a clean abstraction layer for data sources.
Both Google and Mock providers implement the same interface,
allowing seamless switching between data modes.
"""

import json
import os
import random
from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
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


class MockDataProvider(DataProvider):
    """Mock data provider that reads from JSON files"""

    def __init__(self, mock_data_path: str = None):
        # Use relative path for local development, absolute for Docker
        if mock_data_path is None:
            # Check if we're in Docker (absolute path exists) or local (relative path)
            if os.path.exists("/mock_data/accounts.json"):
                self.mock_data_path = "/mock_data"
            else:
                # Local development - use relative path
                self.mock_data_path = os.path.join(os.path.dirname(__file__), "../../mock_data")
        else:
            self.mock_data_path = mock_data_path
        self.accounts_data: List[Dict[str, Any]] = []
        self.locations_data: List[Dict[str, Any]] = []
        self.reviews_data: List[Dict[str, Any]] = []
        self._locations_by_account: Dict[int, List[Dict[str, Any]]] = {}
        self._reviews_by_location: Dict[int, List[Dict[str, Any]]] = {}
        self._load_data()

    def _load_data(self) -> None:
        """Load mock data from JSON files and build indexes"""
        try:
            # Load accounts
            accounts_path = os.path.join(self.mock_data_path, "accounts.json")
            with open(accounts_path, 'r') as f:
                self.accounts_data = json.load(f)

            # Load locations
            locations_path = os.path.join(self.mock_data_path, "locations.json")
            with open(locations_path, 'r') as f:
                self.locations_data = json.load(f)

            # Load reviews
            reviews_path = os.path.join(self.mock_data_path, "reviews.json")
            with open(reviews_path, 'r') as f:
                self.reviews_data = json.load(f)

            # Build indexes for efficient lookup
            self._build_indexes()

            logger.info("Mock data loaded successfully",
                       accounts=len(self.accounts_data),
                       locations=len(self.locations_data),
                       reviews=len(self.reviews_data))

        except FileNotFoundError as e:
            logger.error("Mock data file not found", path=str(e))
            raise
        except json.JSONDecodeError as e:
            logger.error("Invalid JSON in mock data file", error=str(e))
            raise

    def _build_indexes(self) -> None:
        """Build lookup indexes for efficient data retrieval"""
        # Index locations by account_id
        for location in self.locations_data:
            account_id = location.get("google_account_id")
            if account_id not in self._locations_by_account:
                self._locations_by_account[account_id] = []
            self._locations_by_account[account_id].append(location)

        # Index reviews by location_id
        for review in self.reviews_data:
            location_id = review.get("location_id")
            if location_id not in self._reviews_by_location:
                self._reviews_by_location[location_id] = []
            self._reviews_by_location[location_id].append(review)

    async def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """
        Get accounts for mock mode.
        Randomly selects ONE account with account_id between 1-40.
        """
        # Filter accounts with valid account_id range (1-40)
        valid_accounts = [
            account for account in self.accounts_data
            if 1 <= account.get("account_id", 0) <= 40
        ]

        if not valid_accounts:
            logger.warning("No valid accounts found in range 1-40")
            return []

        # Randomly select one account
        selected_account = random.choice(valid_accounts)

        logger.info("Mock mode: Selected random account",
                   account_id=selected_account.get("account_id"),
                   account_name=selected_account.get("account_display_name"))

        return [selected_account]

    async def get_locations(self, account_id: str) -> List[Dict[str, Any]]:
        """Get all locations for the specified account"""
        try:
            account_id_int = int(account_id)
            locations = self._locations_by_account.get(account_id_int, [])

            logger.info("Mock mode: Retrieved locations for account",
                       account_id=account_id_int,
                       locations_count=len(locations))

            return locations
        except (ValueError, TypeError) as e:
            logger.error("Invalid account_id format", account_id=account_id, error=str(e))
            return []

    async def get_reviews(self, location_id: str) -> List[Dict[str, Any]]:
        """Get all reviews for the specified location"""
        try:
            location_id_int = int(location_id)
            reviews = self._reviews_by_location.get(location_id_int, [])

            logger.info("Mock mode: Retrieved reviews for location",
                       location_id=location_id_int,
                       reviews_count=len(reviews))

            return reviews
        except (ValueError, TypeError) as e:
            logger.error("Invalid location_id format", location_id=location_id, error=str(e))
            return []


def get_data_provider(data_mode: str, google_api_client=None) -> DataProvider:
    """
    Factory function to get the appropriate data provider based on mode

    Args:
        data_mode: "google" or "mock"
        google_api_client: Google API client instance (required for google mode)

    Returns:
        DataProvider instance
    """
    if data_mode == "mock":
        return MockDataProvider()
    elif data_mode == "google":
        if google_api_client is None:
            raise ValueError("google_api_client is required for google mode")
        return GoogleDataProvider(google_api_client)
    else:
        raise ValueError(f"Invalid data_mode: {data_mode}. Must be 'google' or 'mock'")