"""
Token Service - Database operations for tokens
"""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from app.token_management.models.token import Token
from app.token_management.models.client import Client
from app.token_management.services.oauth_service import oauth_service

logger = logging.getLogger(__name__)


class TokenService:
    """Service for token database operations"""
    
    @staticmethod
    def create_token(
        db: Session,
        client_id: int,
        access_token: str,
        refresh_token: Optional[str],
        expires_in: Optional[int],
        token_type: str = "Bearer",
        scope: Optional[str] = None,
    ) -> Token:
        """
        Create a new token in database
        
        Args:
            db: Database session
            client_id: Client database ID
            access_token: Access token
            refresh_token: Refresh token (optional)
            expires_in: Seconds until expiry
            token_type: Token type
            scope: Token scope
            
        Returns:
            Created token object
        """
        # Invalidate existing tokens for this client
        TokenService.invalidate_client_tokens(db, client_id)
        
        # Calculate expiry
        expires_at = None
        if expires_in:
            expires_at = oauth_service.calculate_expiry(expires_in)
        
        # Create new token
        token = Token(
            client_id=client_id,
            access_token=access_token,
            refresh_token=refresh_token,
            token_type=token_type,
            scope=scope,
            expires_at=expires_at,
            is_valid=True,
            is_revoked=False,
        )
        
        db.add(token)
        db.commit()
        db.refresh(token)
        
        logger.info(f"Created new token for client_id={client_id}")
        return token
    
    @staticmethod
    def get_valid_token(db: Session, client_id: int) -> Optional[Token]:
        """
        Get valid token for a client
        
        Args:
            db: Database session
            client_id: Client database ID
            
        Returns:
            Valid token or None
        """
        return db.query(Token).filter(
            and_(
                Token.client_id == client_id,
                Token.is_valid == True,
                Token.is_revoked == False,
            )
        ).first()
    
    @staticmethod
    def invalidate_client_tokens(db: Session, client_id: int) -> int:
        """
        Invalidate all tokens for a client
        
        Args:
            db: Database session
            client_id: Client database ID
            
        Returns:
            Number of tokens invalidated
        """
        count = db.query(Token).filter(
            Token.client_id == client_id,
            Token.is_valid == True
        ).update({"is_valid": False})
        
        db.commit()
        logger.info(f"Invalidated {count} tokens for client_id={client_id}")
        return count
    
    @staticmethod
    def revoke_token(db: Session, token_id: int) -> bool:
        """
        Revoke a specific token
        
        Args:
            db: Database session
            token_id: Token ID to revoke
            
        Returns:
            True if token was revoked, False if not found
        """
        token = db.query(Token).filter(Token.id == token_id).first()
        
        if not token:
            return False
        
        token.is_revoked = True
        token.is_valid = False
        db.commit()
        
        logger.info(f"Revoked token id={token_id}")
        return True
    
    @staticmethod
    async def ensure_valid_token(
        db: Session,
        client: Client,
    ) -> Token:
        """
        Ensure client has a valid non-expiring token
        Automatically refreshes if needed
        
        Args:
            db: Database session
            client: Client object
            
        Returns:
            Valid token
            
        Raises:
            Exception: If token refresh fails
        """
        token = TokenService.get_valid_token(db, client.id)
        
        if not token:
            raise Exception("No token found for client")
        
        # Check if token is expiring soon
        if oauth_service.is_token_expiring_soon(token.expires_at):
            logger.info(f"Token expiring soon for client_id={client.id}, refreshing...")
            
            if not token.refresh_token:
                raise Exception("No refresh token available")
            
            # Refresh token
            new_token_data = await oauth_service.refresh_access_token(
                refresh_token=token.refresh_token,
                client_id=client.client_id,
                client_secret=client.client_secret,
            )
            
            # Update token
            token.access_token = new_token_data["access_token"]
            token.token_type = new_token_data.get("token_type", "Bearer")
            token.scope = new_token_data.get("scope", token.scope)
            token.last_refreshed_at = datetime.utcnow()
            
            if new_token_data.get("expires_in"):
                token.expires_at = oauth_service.calculate_expiry(new_token_data["expires_in"])
            
            if new_token_data.get("refresh_token"):
                token.refresh_token = new_token_data["refresh_token"]
            
            db.commit()
            db.refresh(token)
            
            logger.info(f"Token refreshed successfully for client_id={client.id}")
        
        return token


# Create singleton instance
token_service = TokenService()
