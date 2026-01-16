"""
Token Service - Database operations for tokens
"""
from datetime import datetime, timedelta
from typing import Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import and_

from ..models.database import Token, Client
from ..core.logging import get_logger
from .oauth_service import oauth_service

logger = get_logger(__name__)


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
            and_(
                Token.client_id == client_id,
                Token.is_valid == True,
            )
        ).update({"is_valid": False})
        
        db.commit()
        
        if count > 0:
            logger.info(f"Invalidated {count} tokens for client_id={client_id}")
        
        return count
    
    @staticmethod
    def update_token(
        db: Session,
        token: Token,
        access_token: str,
        expires_in: Optional[int],
        refresh_token: Optional[str] = None,
    ) -> Token:
        """
        Update an existing token
        
        Args:
            db: Database session
            token: Token to update
            access_token: New access token
            expires_in: Seconds until expiry
            refresh_token: New refresh token (if provided)
            
        Returns:
            Updated token object
        """
        token.access_token = access_token
        
        if expires_in:
            token.expires_at = oauth_service.calculate_expiry(expires_in)
        
        if refresh_token:
            token.refresh_token = refresh_token
        
        token.last_refreshed_at = datetime.utcnow()
        token.is_valid = True
        
        db.commit()
        db.refresh(token)
        
        logger.info(f"Updated token id={token.id}")
        return token
    
    @staticmethod
    def revoke_token(db: Session, token_id: int) -> bool:
        """
        Revoke a token
        
        Args:
            db: Database session
            token_id: Token database ID
            
        Returns:
            True if revoked successfully
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
        client_id: int,
    ) -> Optional[Token]:
        """
        Ensure client has a valid token, refreshing if necessary
        
        Args:
            db: Database session
            client_id: Client database ID
            
        Returns:
            Valid token or None
        """
        token = TokenService.get_valid_token(db, client_id)
        
        if not token:
            logger.warning(f"No valid token found for client_id={client_id}")
            return None
        
        # Check if token is expiring soon
        if oauth_service.is_token_expiring_soon(token.expires_at):
            logger.info(f"Token expiring soon for client_id={client_id}, attempting refresh")
            
            if not token.refresh_token:
                logger.error(f"No refresh token available for client_id={client_id}")
                token.is_valid = False
                db.commit()
                return None
            
            try:
                # Get client details
                client = db.query(Client).filter(Client.id == client_id).first()
                
                if not client:
                    logger.error(f"Client not found: {client_id}")
                    return None
                
                # Refresh the token
                new_token_data = await oauth_service.refresh_access_token(
                    refresh_token=token.refresh_token,
                    client_id=client.client_id,
                    client_secret=client.client_secret,
                )
                
                # Update token
                token = TokenService.update_token(
                    db=db,
                    token=token,
                    access_token=new_token_data["access_token"],
                    expires_in=new_token_data.get("expires_in"),
                    refresh_token=new_token_data.get("refresh_token", token.refresh_token),
                )
                
                logger.info(f"Successfully refreshed token for client_id={client_id}")
                
            except Exception as e:
                logger.error(f"Failed to refresh token for client_id={client_id}: {str(e)}")
                token.is_valid = False
                db.commit()
                return None
        
        return token
    
    @staticmethod
    def cleanup_expired_tokens(db: Session) -> int:
        """
        Clean up expired tokens (for maintenance)
        
        Args:
            db: Database session
            
        Returns:
            Number of tokens cleaned up
        """
        count = db.query(Token).filter(
            and_(
                Token.expires_at < datetime.utcnow(),
                Token.is_valid == True,
            )
        ).update({"is_valid": False})
        
        db.commit()
        
        if count > 0:
            logger.info(f"Cleaned up {count} expired tokens")
        
        return count


# Create singleton instance
token_service = TokenService()
