import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings
from app.utils.cache import cache_get, cache_set
import structlog

logger = structlog.get_logger()


class GoogleAPIError(Exception):
    pass

class GoogleAPIClient:
    def __init__(self):
        self.client = httpx.AsyncClient(timeout=30.0)

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
        """Mock implementation - returns sample accounts"""
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
        """Mock implementation - returns sample locations"""
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
        """Mock implementation - returns sample reviews"""
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