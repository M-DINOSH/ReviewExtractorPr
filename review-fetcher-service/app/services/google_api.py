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
            # Use Google's tokeninfo endpoint for validation
            url = f"https://www.googleapis.com/oauth2/v1/tokeninfo?access_token={access_token}"
            response = await self.client.get(url)
            response.raise_for_status()
            return response.json()
        except Exception:
            # If tokeninfo fails, try a lightweight API call
            try:
                # Test with a minimal API call that doesn't count against quota
                test_url = "https://www.googleapis.com/oauth2/v1/userinfo?alt=json"
                headers = {"Authorization": f"Bearer {access_token}"}
                response = await self.client.get(test_url, headers=headers)
                response.raise_for_status()
                return {"valid": True}
            except Exception:
                raise

    async def get_locations(self, account_id: str, access_token: str):
        cache_key = f"locations:{account_id}"
        cached = await cache_get(cache_key)
        if cached:
            return cached

        url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
        data = await self._get(url, access_token)
        await cache_set(cache_key, data, ttl=3600)
        return data

    async def get_reviews(self, account_id: str, location_id: str, access_token: str):
        url = f"https://mybusiness.googleapis.com/v4/{account_id}/locations/{location_id}/reviews"
        return await self._get(url, access_token)

    async def close(self):
        await self.client.aclose()

# Global instance
google_api_client = GoogleAPIClient()