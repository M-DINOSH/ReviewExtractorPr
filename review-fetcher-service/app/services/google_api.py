import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings
from app.utils.cache import cache_get, cache_set
import structlog
import json
import os
from typing import Dict, List, Any

logger = structlog.get_logger()


class MockDataLoader:
    """Loads and provides mock data from JSON files"""

    def __init__(self):
        self.accounts_data = []
        self.locations_data = []
        self.reviews_data = []
        self._load_data()

    def _load_data(self):
        """Load data from JSON files"""
        try:
            # Load accounts
            accounts_path = os.path.join(os.path.dirname(__file__), '../../json/accounts.json')
            with open(accounts_path, 'r') as f:
                self.accounts_data = json.load(f)

            # Load locations
            locations_path = os.path.join(os.path.dirname(__file__), '../../json/locations.json')
            with open(locations_path, 'r') as f:
                self.locations_data = json.load(f)

            # Load reviews
            reviews_path = os.path.join(os.path.dirname(__file__), '../../json/Reviews.json')
            with open(reviews_path, 'r') as f:
                self.reviews_data = json.load(f)

            logger.info("Mock data loaded successfully",
                       accounts=len(self.accounts_data),
                       locations=len(self.locations_data),
                       reviews=len(self.reviews_data))

        except Exception as e:
            logger.error("Failed to load mock data", error=str(e))
            raise

    def get_accounts_for_client(self, client_id: str) -> List[Dict]:
        """Get accounts for a specific client"""
        # For demo purposes, return a subset of accounts based on client_id hash
        import hashlib
        client_hash = int(hashlib.md5(client_id.encode()).hexdigest()[:2], 16)
        start_idx = client_hash % max(1, len(self.accounts_data) // 3)
        end_idx = min(start_idx + 3, len(self.accounts_data))

        accounts = []
        for account in self.accounts_data[start_idx:end_idx]:
            accounts.append({
                "name": account["google_account_name"],
                "accountName": account["account_display_name"],
                "type": "BUSINESS"
            })
        return accounts

    def get_locations_for_account(self, account_name: str) -> List[Dict]:
        """Get locations for a specific account"""
        account_id = account_name.split('/')[-1]
        
        # Extract original account ID from unique account ID (format: original_id_sync_job_id)
        if '_' in account_id:
            original_account_id = account_id.split('_')[0]
        else:
            original_account_id = account_id

        locations = []
        # Get a subset of locations based on account_id hash to avoid duplicates
        account_hash = int(original_account_id[-2:], 16) if len(original_account_id) >= 2 else int(original_account_id[-1]) if original_account_id else 0
        start_idx = account_hash % max(1, len(self.locations_data) // 5)
        end_idx = min(start_idx + 5, len(self.locations_data))

        for i, location in enumerate(self.locations_data[start_idx:end_idx]):
            # Generate unique location ID by combining account and location
            unique_location_id = f"{location['location_name'].split('/')[-1]}_{original_account_id[-4:]}_{i}"

            locations.append({
                "name": f"locations/{unique_location_id}",
                "locationName": location["location_title"],
                "address": {
                    "formatted_address": location["address"],
                    "locality": location["address"].split(',')[0].strip(),
                    "region": location["address"].split(',')[-2].strip() if len(location["address"].split(',')) > 1 else "",
                    "country": "IN"
                }
            })

        # Ensure we have at least 2-3 locations per account
        if len(locations) < 3:
            # Add more locations if needed
            additional_start = (start_idx + 10) % len(self.locations_data)
            for i, location in enumerate(self.locations_data[additional_start:additional_start + (3 - len(locations))]):
                unique_location_id = f"{location['location_name'].split('/')[-1]}_{account_id[-4:]}_{i}"
                locations.append({
                    "name": f"locations/{unique_location_id}",
                    "locationName": location["location_title"],
                    "address": {
                        "formatted_address": location["address"],
                        "locality": location["address"].split(',')[0].strip(),
                        "region": location["address"].split(',')[-2].strip() if len(location["address"].split(',')) > 1 else "",
                        "country": "IN"
                    }
                })

        return locations[:5]  # Limit to 5 locations per account

    def get_reviews_for_location(self, location_name: str) -> List[Dict]:
        """Get reviews for a specific location"""
        # Extract the original location ID from the unique location name
        location_parts = location_name.split('/')[-1].split('_')
        original_location_id = location_parts[0]

        reviews = []
        for review in self.reviews_data:
            # Match by location_id
            if str(review.get("location_id", "")).endswith(str(original_location_id)[-3:]):
                # Convert rating number to Google API format
                rating_map = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE"}
                star_rating = rating_map.get(review["rating"], "FIVE")

                reviews.append({
                    "reviewId": review["google_review_id"],
                    "starRating": star_rating,
                    "comment": review["comment"],
                    "createTime": review["review_created_time"],
                    "reviewer": {
                        "displayName": review["reviewer_name"]
                    }
                })

        # If no matches found, return reviews based on location hash
        if not reviews:
            import hashlib
            location_hash = int(hashlib.md5(location_name.encode()).hexdigest()[:4], 16)
            start_idx = location_hash % max(1, len(self.reviews_data) // 10)
            for review in self.reviews_data[start_idx:start_idx + 10]:
                rating_map = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE"}
                star_rating = rating_map.get(review["rating"], "FIVE")

                reviews.append({
                    "reviewId": review["google_review_id"],
                    "starRating": star_rating,
                    "comment": review["comment"],
                    "createTime": review["review_created_time"],
                    "reviewer": {
                        "displayName": review["reviewer_name"]
                    }
                })

        return reviews[:15]  # Limit to 15 reviews per location


class GoogleAPIError(Exception):
    pass

class GoogleAPIClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)
        self.mock_data_loader = None
        if settings.mock_mode:
            self.mock_data_loader = MockDataLoader()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
    async def _get(self, url: str, access_token: str):
        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def validate_token(self, access_token: str):
        """Validate access token using Google's tokeninfo endpoint"""
        try:
            # For demo purposes, accept any token that starts with 'ya29' or 'mock_'
            # In production, this should validate with Google APIs
            if access_token.startswith('ya29') or access_token.startswith('mock_'):
                logger.info("Token validation bypassed for demo", token_prefix=access_token[:10])
                return {"valid": True, "demo": True}
            else:
                raise GoogleAPIError("Invalid token format")

        except Exception as e:
            logger.error("Token validation failed", error=str(e))
            raise

    async def get_accounts(self, access_token: str):
        """Get accounts - uses mock data if in mock mode"""
        if self.mock_data_loader:
            logger.info("Using mock data for accounts")
            # Extract client_id from access_token (for demo, use token hash)
            import hashlib
            client_id = hashlib.md5(access_token.encode()).hexdigest()[:8]
            accounts = self.mock_data_loader.get_accounts_for_client(client_id)
            return {"accounts": accounts}
        else:
            logger.info("Mock get_accounts called")
            # Generate unique account ID based on access token hash for demo purposes
            import hashlib
            account_id = str(int(hashlib.md5(access_token.encode()).hexdigest()[:8], 16))
            return {
                "accounts": [
                    {
                        "name": f"accounts/{account_id}",
                        "accountName": "Demo Business Account",
                        "type": "BUSINESS"
                    }
                ]
            }

    async def get_locations(self, account_id: str, access_token: str):
        """Get locations - uses mock data if in mock mode"""
        if self.mock_data_loader:
            logger.info("Using mock data for locations", account_id=account_id)
            locations = self.mock_data_loader.get_locations_for_account(account_id)
            return {"locations": locations}
        else:
            logger.info("Mock get_locations called", account_id=account_id)
            # Extract account ID number and generate unique location ID
            account_num = account_id.split('/')[-1]
            location_id = f"locations/{int(account_num) + 100000000}"
            return {
                "locations": [
                    {
                        "name": location_id,
                        "locationName": "Demo Restaurant",
                        "address": {
                            "locality": "New York",
                            "region": "NY"
                        }
                    }
                ]
            }

    async def get_reviews(self, account_id: str, location_id: str, access_token: str):
        """Get reviews - uses mock data if in mock mode"""
        if self.mock_data_loader:
            logger.info("Using mock data for reviews", account_id=account_id, location_id=location_id)
            reviews = self.mock_data_loader.get_reviews_for_location(location_id)
            return {"reviews": reviews}
        else:
            logger.info("Mock get_reviews called", account_id=account_id, location_id=location_id)
            # Generate unique review ID based on location_id
            import hashlib
            review_id = hashlib.md5(f"{location_id}_review".encode()).hexdigest()[:20]
            return {
                "reviews": [
                    {
                        "reviewId": f"ChdDSUhNMG9nS0VJQ0FnSUR{review_id}",
                        "starRating": "FIVE",
                        "comment": "Great food and service!",
                        "createTime": "2023-01-01T12:00:00Z",
                        "reviewer": {
                            "displayName": "John Doe"
                        }
                    }
                ]
            }

    async def close(self):
        await self.client.aclose()

# Global instance
google_api_client = GoogleAPIClient()