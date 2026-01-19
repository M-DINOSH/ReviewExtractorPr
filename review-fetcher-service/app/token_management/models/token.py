"""Token model stored in token management database"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean, Text, Index, ForeignKey
from sqlalchemy.orm import relationship
from app.token_management.database.config import Base


class Token(Base):
    __tablename__ = "tokens"
    __table_args__ = (
        Index("ix_tokens_client_valid", "client_id", "is_valid"),
        Index("ix_tokens_expires_at", "expires_at"),
        {"extend_existing": True},
    )

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(Integer, ForeignKey("clients.id", ondelete="CASCADE"), nullable=False)

    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)
    token_type = Column(String(50), default="Bearer", nullable=False)
    scope = Column(Text, nullable=True)

    expires_at = Column(DateTime, nullable=True)
    is_valid = Column(Boolean, default=True, nullable=False)
    is_revoked = Column(Boolean, default=False, nullable=False)
    last_refreshed_at = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    client = relationship("Client", back_populates="tokens")

    def __repr__(self) -> str:
        return f"<Token(id={self.id}, client_id={self.client_id}, is_valid={self.is_valid})>"
