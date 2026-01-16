"""
Database models for Token Generation Service
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, DateTime, Boolean, 
    Text, ForeignKey, Index
)
from sqlalchemy.orm import relationship

from ..core.database import Base


class Client(Base):
    """OAuth Client configuration"""
    __tablename__ = "clients"
    
    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(255), unique=True, nullable=False, index=True)
    client_secret = Column(String(512), nullable=False)
    redirect_uri = Column(String(512), nullable=False)
    
    # Request body fields
    branch_id = Column(String(255), unique=True, nullable=False, index=True)
    workspace_email = Column(String(255), nullable=False)
    workspace_name = Column(String(255), nullable=False)
    
    # Metadata
    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    
    # Relationships
    tokens = relationship("Token", back_populates="client", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Client(id={self.id}, client_id={self.client_id}, branch_id={self.branch_id})>"


class Token(Base):
    """OAuth tokens storage"""
    __tablename__ = "tokens"
    
    id = Column(Integer, primary_key=True, index=True)
    
    # Client association
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)
    
    # Token data
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), default="Bearer", nullable=False)
    scope = Column(Text, nullable=True)
    
    # Expiry tracking
    expires_at = Column(DateTime, nullable=True)  # When access token expires
    
    # Status
    is_valid = Column(Boolean, default=True, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    
    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    last_refreshed_at = Column(DateTime, nullable=True)
    
    # Relationships
    client = relationship("Client", back_populates="tokens")
    
    # Indexes
    __table_args__ = (
        Index('ix_tokens_client_valid', 'client_id', 'is_valid'),
        Index('ix_tokens_expires_at', 'expires_at'),
    )
    
    def __repr__(self):
        return f"<Token(id={self.id}, client_id={self.client_id}, is_valid={self.is_valid})>"
