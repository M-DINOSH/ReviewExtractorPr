import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from app.config import settings
import structlog
from typing import Dict, List, Any

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
            # Validate that token starts with 'ya29' (Google OAuth tokens)
            if not access_token.startswith('ya29'):
                raise GoogleAPIError("Invalid token format. Must be a valid Google OAuth token starting with 'ya29'")

            # Test token by making a simple API call to accounts endpoint
            try:
                await self._get("https://mybusinessbusinessinformation.googleapis.com/v1/accounts", access_token)
                logger.info("Token validation successful")
                return {"valid": True}
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 401:
                    raise GoogleAPIError("Invalid or expired access token")
                elif e.response.status_code == 403:
                    raise GoogleAPIError("Insufficient permissions. Token needs Google Business Profile API access")
                else:
                    raise GoogleAPIError(f"Token validation failed: {e.response.status_code}")

        except httpx.HTTPStatusError:
            raise
        except Exception as e:
            logger.error("Token validation failed: %s", str(e))
            raise GoogleAPIError(f"Token validation failed: {str(e)}")

    async def get_accounts(self, access_token: str):
        """Get accounts from Google Business Profile API"""
        try:
            url = "https://mybusinessbusinessinformation.googleapis.com/v1/accounts"
            response_data = await self._get(url, access_token)

            accounts_count = len(response_data.get("accounts", []))
            logger.info("Successfully fetched accounts from Google API (count=%d)", accounts_count)

            return response_data

        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to fetch accounts from Google API (status=%s, body=%s)",
                e.response.status_code,
                e.response.text,
            )
            if e.response.status_code == 401:
                raise GoogleAPIError("Unauthorized: Invalid access token")
            elif e.response.status_code == 403:
                raise GoogleAPIError("Forbidden: Insufficient permissions for Business Profile API")
            else:
                raise GoogleAPIError(f"Google API error: {e.response.status_code}")
        except Exception as e:
            logger.error("Unexpected error fetching accounts: %s", str(e))
            raise GoogleAPIError(f"Failed to fetch accounts: {str(e)}")

    async def get_locations(self, account_id: str, access_token: str):
        """Get locations for account from Google Business Profile API"""
        try:
            # Extract account name from full account resource name if needed
            if not account_id.startswith("accounts/"):
                account_id = f"accounts/{account_id}"

            url = f"https://mybusinessbusinessinformation.googleapis.com/v1/{account_id}/locations"
            response_data = await self._get(url, access_token)

            locations_count = len(response_data.get("locations", []))
            logger.info(
                "Successfully fetched locations from Google API (account=%s, count=%d)",
                account_id,
                locations_count,
            )

            return response_data

        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to fetch locations from Google API (account=%s, status=%s, body=%s)",
                account_id,
                e.response.status_code,
                e.response.text,
            )
            if e.response.status_code == 401:
                raise GoogleAPIError("Unauthorized: Invalid access token")
            elif e.response.status_code == 403:
                raise GoogleAPIError("Forbidden: No access to this account's locations")
            else:
                raise GoogleAPIError(f"Google API error: {e.response.status_code}")
        except Exception as e:
            logger.error("Unexpected error fetching locations for %s: %s", account_id, str(e))
            raise GoogleAPIError(f"Failed to fetch locations: {str(e)}")

    async def get_reviews(self, account_id: str, location_id: str, access_token: str):
        """Get reviews for location from Google My Business API"""
        try:
            # Extract account and location IDs from resource names if needed
            if not account_id.startswith("accounts/"):
                account_id = f"accounts/{account_id}"
            if not location_id.startswith("locations/"):
                location_id = f"locations/{location_id}"

            url = f"https://mybusiness.googleapis.com/v4/{account_id}/{location_id}/reviews"
            response_data = await self._get(url, access_token)

            reviews_count = len(response_data.get("reviews", []))
            logger.info(
                "Successfully fetched reviews from Google API (account=%s, location=%s, count=%d)",
                account_id,
                location_id,
                reviews_count,
            )

            return response_data

        except httpx.HTTPStatusError as e:
            logger.error(
                "Failed to fetch reviews from Google API (account=%s, location=%s, status=%s, body=%s)",
                account_id,
                location_id,
                e.response.status_code,
                e.response.text,
            )
            if e.response.status_code == 401:
                raise GoogleAPIError("Unauthorized: Invalid access token")
            elif e.response.status_code == 403:
                raise GoogleAPIError("Forbidden: No access to this location's reviews")
            else:
                raise GoogleAPIError(f"Google API error: {e.response.status_code}")
        except Exception as e:
            logger.error(
                "Unexpected error fetching reviews for account=%s location=%s: %s",
                account_id,
                location_id,
                str(e),
            )
            raise GoogleAPIError(f"Failed to fetch reviews: {str(e)}")

    async def close(self):
        await self.client.aclose()

# Global instance
google_api_client = GoogleAPIClient()