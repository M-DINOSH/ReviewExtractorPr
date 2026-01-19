"""Client model stored in token management database"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Boolean
from sqlalchemy.orm import relationship
from app.token_management.database.config import Base


class Client(Base):
    __tablename__ = "clients"
    __table_args__ = {'extend_existing': True}

    id = Column(Integer, primary_key=True, index=True)
    client_id = Column(String(255), unique=True, nullable=False, index=True)
    client_secret = Column(String(512), nullable=False)
    redirect_uri = Column(String(512), nullable=False)

    branch_id = Column(String(255), unique=True, nullable=False, index=True)
    workspace_email = Column(String(255), nullable=False)
    workspace_name = Column(String(255), nullable=False)

    is_active = Column(Boolean, default=True, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    tokens = relationship("Token", back_populates="client", cascade="all, delete-orphan")

    def __repr__(self) -> str:
        return f"<Client(id={self.id}, client_id={self.client_id}, branch_id={self.branch_id})>"
