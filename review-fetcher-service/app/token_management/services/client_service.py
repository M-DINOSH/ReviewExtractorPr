"""
Client Service - Database operations for OAuth clients
"""
from typing import Optional, List
from sqlalchemy.orm import Session
import logging

from app.token_management.models.client import Client

logger = logging.getLogger(__name__)


class ClientService:
    """Service for client database operations"""
    
    @staticmethod
    def get_client_by_id(db: Session, client_id: int) -> Optional[Client]:
        """Get client by internal ID"""
        return db.query(Client).filter(Client.id == client_id).first()
    
    @staticmethod
    def get_client_by_client_id(db: Session, client_id: str) -> Optional[Client]:
        """Get client by OAuth client_id"""
        return db.query(Client).filter(Client.client_id == client_id).first()
    
    @staticmethod
    def get_client_by_branch_id(db: Session, branch_id: str) -> Optional[Client]:
        """Get client by branch_id"""
        return db.query(Client).filter(Client.branch_id == branch_id).first()
    
    @staticmethod
    def list_clients(db: Session, skip: int = 0, limit: int = 100) -> List[Client]:
        """List all clients"""
        return db.query(Client).offset(skip).limit(limit).all()
    
    @staticmethod
    def delete_client(db: Session, client_id: int) -> bool:
        """Delete a client"""
        client = db.query(Client).filter(Client.id == client_id).first()
        
        if not client:
            return False
        
        db.delete(client)
        db.commit()
        
        logger.info(f"Deleted client id={client_id}")
        return True


# Create singleton instance
client_service = ClientService()
