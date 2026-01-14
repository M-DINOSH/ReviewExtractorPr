import httpx

try:
    from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
except Exception:  # pragma: no cover
    retry = None
    stop_after_attempt = None
    wait_exponential = None
    retry_if_exception_type = None


def _retry_decorator():
    if retry is None:
        return lambda fn: fn
    return retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=4, max=10),
        retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError)),
    )
from app.config import settings
import structlog
from typing import Dict, List, Any
from app.services.mock_data import mock_data_service

logger = structlog.get_logger()


class GoogleAPIError(Exception):
    pass


class GoogleAPIClient:
    def __init__(self, use_mock: bool = None):
        self.client = httpx.AsyncClient(timeout=30.0)
        # Use mock mode from config if not explicitly set
        self.use_mock = use_mock if use_mock is not None else settings.mock_google_api
        
        logger.info(f"GoogleAPIClient init: use_mock={use_mock}, settings.mock_google_api={settings.mock_google_api}, final use_mock={self.use_mock}")
        if self.use_mock:
            logger.info("GoogleAPIClient initialized in MOCK mode - using data from jsom folder")
        else:
            logger.warning("GoogleAPIClient initialized in REAL mode - will call actual Google APIs")

    @_retry_decorator()
    async def _get(self, url: str, access_token: str):
        if retry is None and not self.use_mock:
            raise GoogleAPIError(
                "Missing dependency 'tenacity'. Install it to use real Google API mode."
            )

        headers = {"Authorization": f"Bearer {access_token}"}
        response = await self.client.get(url, headers=headers)
        response.raise_for_status()
        return response.json()

    async def validate_token(self, access_token: str):
        """Validate access token - in mock mode, accept any token"""
        # In mock mode, accept any token that's at least 10 chars
        if self.use_mock:
            logger.info("Token validation skipped in mock mode", token_length=len(access_token))
            return {"valid": True}
        
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
            logger.error("Token validation failed", error=str(e))
            raise GoogleAPIError(f"Token validation failed: {str(e)}")

    async def get_accounts(self, access_token: str):
        """Get accounts from Google Business Profile API or mock data"""
        # Use mock data if in mock mode
        if self.use_mock:
            logger.info("Fetching accounts from mock data")
            return await mock_data_service.get_accounts(access_token)
        
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
        """Get locations for account from Google Business Profile API or mock data"""
        # Use mock data if in mock mode
        if self.use_mock:
            logger.info("Fetching locations from mock data for account=%s", account_id)
            return await mock_data_service.get_locations(account_id, access_token)
        
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
        """Get reviews for location from Google My Business API or mock data"""
        # Use mock data if in mock mode
        if self.use_mock:
            logger.info("Fetching reviews from mock data for account=%s, location=%s", account_id, location_id)
            return await mock_data_service.get_reviews(account_id, location_id, access_token)
        
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