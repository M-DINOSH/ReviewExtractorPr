"""
Mock Data Service - Loads and serves mock data from JSON files
"""

import json
from typing import Dict, List, Any, Optional
import structlog
from pathlib import Path

logger = structlog.get_logger()


class MockDataService:
    """Service to load and serve mock data from jsom folder"""
    
    def __init__(self):
        base_dir = Path(__file__).parent.parent.parent
        self.data_dir = base_dir / "jsom"
        
        self.accounts_data: List[Dict] = []
        self.locations_data: List[Dict] = []
        self.reviews_data: List[Dict] = []
        
        self._load_mock_data()
    
    def _load_mock_data(self):
        """Load JSON files from jsom folder"""
        try:
            # Load accounts.json
            accounts_file = self.data_dir / "accounts.json"
            with open(accounts_file, 'r', encoding='utf-8') as f:
                self.accounts_data = json.load(f)
            
            # Load locations.json
            locations_file = self.data_dir / "locations.json"
            with open(locations_file, 'r', encoding='utf-8') as f:
                self.locations_data = json.load(f)
            
            # Load Reviews.json
            reviews_file = self.data_dir / "Reviews.json"
            with open(reviews_file, 'r', encoding='utf-8') as f:
                self.reviews_data = json.load(f)
                
        except Exception as e:
            logger.error("mock_data_load_error", error=str(e))
            raise
    
    async def get_accounts(self) -> List[Dict[str, Any]]:
        """Return all accounts from jsom/accounts.json"""
        accounts = []
        for account in self.accounts_data:
            accounts.append({
                # Original fields expected by existing workers
                "id": account["id"],
                "name": account["google_account_name"],
                "display_name": account["account_display_name"],

                # Full schema fields (used by demo/web output)
                "account_id": account.get("account_id", account["id"]),
                "client_id": account.get("client_id"),
                "google_account_name": account.get("google_account_name"),
                "account_display_name": account.get("account_display_name"),
                "created_at": account.get("created_at"),
                "updated_at": account.get("updated_at"),
            })
        return accounts
    
    async def get_locations(self, account_id: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Return locations for an account.
        If account_id is None, return all locations.
        """
        if account_id is None:
            return self.locations_data
        
        # Filter by google_account_id
        account_id_str = str(account_id)
        filtered = [
            loc for loc in self.locations_data 
            if str(loc.get("google_account_id")) == account_id_str
        ]
        return filtered
    
    async def get_reviews(
        self, 
        location_id: int,
        page_size: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Return reviews for a location.
        Filters by location_id and returns up to page_size reviews.
        """
        location_id_str = str(location_id)
        filtered = [
            review for review in self.reviews_data
            if str(review.get("location_id")) == location_id_str
        ]
        return filtered[:page_size]

# Global instance
mock_data_service = MockDataService()
