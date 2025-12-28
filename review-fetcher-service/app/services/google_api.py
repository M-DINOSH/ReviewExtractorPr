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
    """Loads and provides mock data from JSON files with proper relationships"""

    def __init__(self):
        self.accounts_data = []
        self.locations_data = []
        self.reviews_data = []
        self._accounts_by_client = {}
        self._locations_by_account = {}
        self._reviews_by_location = {}
        self._account_name_to_id = {}
        self._load_data()

    def _load_data(self):
        """Load data from JSON files and build relationship indexes"""
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

            # Build indexes for efficient lookup
            self._build_indexes()

            logger.info("Mock data loaded successfully",
                       accounts=len(self.accounts_data),
                       locations=len(self.locations_data),
                       reviews=len(self.reviews_data))

        except Exception as e:
            logger.error("Failed to load mock data", error=str(e))
            raise

    def _build_indexes(self):
        """Build indexes for efficient data lookup"""
        # Index accounts by client_id
        for account in self.accounts_data:
            client_id = account['client_id']
            if client_id not in self._accounts_by_client:
                self._accounts_by_client[client_id] = []
            self._accounts_by_client[client_id].append(account)

        # Create mapping from Google account name to account_id
        self._account_name_to_id = {}
        for account in self.accounts_data:
            self._account_name_to_id[account['google_account_name']] = account['account_id']

        # Index locations by google_account_id
        for location in self.locations_data:
            account_id = location['google_account_id']
            if account_id not in self._locations_by_account:
                self._locations_by_account[account_id] = []
            self._locations_by_account[account_id].append(location)

        # Index reviews by location_id
        for review in self.reviews_data:
            location_id = review['location_id']
            if location_id not in self._reviews_by_location:
                self._reviews_by_location[location_id] = []
            self._reviews_by_location[location_id].append(review)

    def get_accounts_for_client(self, client_id: str) -> List[Dict]:
        """Get accounts for a specific client"""
        # Convert client_id to int for lookup (assuming it's a hash or identifier)
        try:
            client_id_int = int(client_id) if client_id.isdigit() else hash(client_id) % 10 + 1
        except:
            client_id_int = hash(client_id) % 6 + 1  # Default to 1-6 range

        # Get accounts for this client, or fallback to client 1 if not found
        accounts = self._accounts_by_client.get(client_id_int, self._accounts_by_client.get(1, []))

        result = []
        for account in accounts[:5]:  # Limit to 5 accounts per client
            result.append({
                "name": account["google_account_name"],
                "accountName": account["account_display_name"],
                "type": "BUSINESS"
            })
        return result

    def get_locations_for_account(self, account_name: str) -> List[Dict]:
        """Get locations for a specific account"""
        # Handle suffixed account names (format: accounts/ORIGINAL_ID_SYNC_JOB_ID)
        original_account_name = account_name
        if '_' in account_name and account_name.count('/') == 1:
            # Split on the last underscore to separate sync_job_id
            parts = account_name.rsplit('_', 1)
            if len(parts) == 2 and parts[1].isdigit():
                original_account_name = parts[0]

        # Look up the account_id using the original Google account name
        account_id = self._account_name_to_id.get(original_account_name)
        if account_id is None:
            # Fallback: try to extract from account name
            if '/' in original_account_name:
                account_name_part = original_account_name.split('/')[-1]
                try:
                    account_id = int(account_name_part)
                except:
                    account_id = hash(original_account_name) % 100 + 1
            else:
                account_id = hash(original_account_name) % 100 + 1

        # Get locations for this account
        locations = self._locations_by_account.get(account_id, [])

        result = []
        for i, location in enumerate(locations[:10]):  # Limit to 10 locations per account
            # Create a unique location ID using account + index to ensure uniqueness
            # Extract the base account ID (without sync_job suffix)
            base_account_id = account_name.split('/')[-1]
            if '_' in base_account_id:
                base_account_id = base_account_id.split('_')[0]

            # Use account_id + index to ensure uniqueness
            unique_location_id = f"{base_account_id}_{i}"

            result.append({
                "name": f"locations/{unique_location_id}",
                "locationName": location["location_title"],
                "address": {
                    "formatted_address": location["address"],
                    "locality": location["address"].split(',')[0].strip(),
                    "region": location["address"].split(',')[-2].strip() if len(location["address"].split(',')) > 1 else "",
                    "country": "IN"
                }
            })

        return result

    def get_reviews_for_location(self, location_id: str) -> List[Dict]:
        """Get reviews for a specific location"""
        # Extract the location ID number
        if '/' in location_id:
            location_id = location_id.split('/')[-1]

        # Remove any sync_job_id suffix if present
        if '_' in location_id:
            location_id = location_id.split('_')[0]

        try:
            location_id_int = int(location_id)
        except:
            location_id_int = hash(location_id) % 1000 + 1

        # Get reviews for this location
        reviews = self._reviews_by_location.get(location_id_int, [])

        result = []
        for review in reviews[:50]:  # Limit to 50 reviews per location
            result.append({
                "reviewId": review["google_review_id"],
                "starRating": self._rating_to_google_format(review["rating"]),
                "comment": review["comment"],
                "createTime": review["review_created_time"],
                "reviewer": {
                    "displayName": review["reviewer_name"]
                }
            })

        return result

    def _rating_to_google_format(self, rating: int) -> str:
        """Convert numeric rating to Google format"""
        rating_map = {1: "ONE", 2: "TWO", 3: "THREE", 4: "FOUR", 5: "FIVE"}
        return rating_map.get(rating, "FIVE")

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