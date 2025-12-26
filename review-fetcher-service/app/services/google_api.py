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

    async def get_accounts(self, access_token: str):
        cache_key = f"accounts:{access_token[:10]}"  # Partial token for cache key
        cached = await cache_get(cache_key)
        if cached:
            return cached

        url = "https://mybusinessaccountmanagement.googleapis.com/v1/accounts"
        data = await self._get(url, access_token)
        await cache_set(cache_key, data, ttl=3600)  # Cache for 1 hour
        return data

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