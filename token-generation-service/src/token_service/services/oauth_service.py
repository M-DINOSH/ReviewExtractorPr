"""
OAuth Service - Handles Google OAuth token exchange and refresh
"""
import httpx
from datetime import datetime, timedelta
from typing import Dict, Optional

from ..core.config import settings
from ..core.logging import get_logger

logger = get_logger(__name__)


class OAuthService:
    """Service for Google OAuth operations"""
    
    def __init__(self):
        self.token_url = settings.GOOGLE_TOKEN_URL
        self.timeout = 20
    
    async def exchange_code_for_token(
        self,
        code: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> Dict:
        """
        Exchange authorization code for access and refresh tokens
        
        Args:
            code: Authorization code from Google
            client_id: OAuth client ID
            client_secret: OAuth client secret
            redirect_uri: Redirect URI used in authorization
            
        Returns:
            Token response from Google
            
        Raises:
            httpx.HTTPError: If token exchange fails
        """
        payload = {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
        
        logger.info(f"Exchanging authorization code for tokens (client_id: {client_id[:20]}...)")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.token_url, data=payload)
                response.raise_for_status()
                token_data = response.json()
                
                logger.info("Successfully exchanged code for tokens")
                return token_data
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to exchange code for token: {str(e)}")
                raise
    
    async def refresh_access_token(
        self,
        refresh_token: str,
        client_id: str,
        client_secret: str,
    ) -> Dict:
        """
        Refresh an access token using a refresh token
        
        Args:
            refresh_token: The refresh token
            client_id: OAuth client ID
            client_secret: OAuth client secret
            
        Returns:
            New token response from Google
            
        Raises:
            httpx.HTTPError: If token refresh fails
        """
        payload = {
            "refresh_token": refresh_token,
            "client_id": client_id,
            "client_secret": client_secret,
            "grant_type": "refresh_token",
        }
        
        logger.info(f"Refreshing access token (client_id: {client_id[:20]}...)")
        
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.post(self.token_url, data=payload)
                response.raise_for_status()
                token_data = response.json()
                
                logger.info("Successfully refreshed access token")
                return token_data
                
            except httpx.HTTPError as e:
                logger.error(f"Failed to refresh token: {str(e)}")
                raise
    
    @staticmethod
    def calculate_expiry(expires_in: int) -> datetime:
        """
        Calculate token expiry datetime
        
        Args:
            expires_in: Seconds until token expires
            
        Returns:
            Datetime when token expires
        """
        return datetime.utcnow() + timedelta(seconds=expires_in)
    
    @staticmethod
    def is_token_expiring_soon(expires_at: Optional[datetime], buffer_seconds: int = None) -> bool:
        """
        Check if token is expiring soon
        
        Args:
            expires_at: Token expiry datetime
            buffer_seconds: Buffer time in seconds (default from settings)
            
        Returns:
            True if token is expiring within buffer time
        """
        if not expires_at:
            return True
        
        if buffer_seconds is None:
            buffer_seconds = settings.TOKEN_EXPIRY_BUFFER
        
        buffer_time = datetime.utcnow() + timedelta(seconds=buffer_seconds)
        return expires_at <= buffer_time


# Create singleton instance
oauth_service = OAuthService()
