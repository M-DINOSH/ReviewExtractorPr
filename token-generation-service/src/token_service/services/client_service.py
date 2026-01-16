"""
Client Service - Database operations
"""
from typing import Optional, List
from sqlalchemy.orm import Session

from ..models.database import Client
from ..models.schemas import ClientCreate, ClientUpdate
from ..core.logging import get_logger

logger = get_logger(__name__)


class ClientService:
    """Service for client database operations"""
    
    @staticmethod
    def create_client(db: Session, client_data: ClientCreate) -> Client:
        """
        Create a new client
        
        Args:
            db: Database session
            client_data: Client creation data
            
        Returns:
            Created client object
        """
        client = Client(
            client_id=client_data.client_id,
            client_secret=client_data.client_secret,
            redirect_uri=str(client_data.redirect_uri),
        )
        
        db.add(client)
        db.commit()
        db.refresh(client)
        
        logger.info(f"Created new client: {client.client_id}")
        return client
    
    @staticmethod
    def get_client_by_id(db: Session, client_id: int) -> Optional[Client]:
        """Get client by internal ID"""
        return db.query(Client).filter(Client.id == client_id).first()
    
    @staticmethod
    def get_client_by_client_id(db: Session, client_id: str) -> Optional[Client]:
        """Get client by OAuth client_id"""
        return db.query(Client).filter(Client.client_id == client_id).first()
    
    @staticmethod
    def list_clients(db: Session, skip: int = 0, limit: int = 100) -> List[Client]:
        """List all clients"""
        return db.query(Client).offset(skip).limit(limit).all()
    
    @staticmethod
    def update_client(db: Session, client: Client, update_data: ClientUpdate) -> Client:
        """
        Update client information
        
        Args:
            db: Database session
            client: Client to update
            update_data: Update data
            
        Returns:
            Updated client object
        """
        update_dict = update_data.model_dump(exclude_unset=True)
        
        for field, value in update_dict.items():
            setattr(client, field, value)
        
        db.commit()
        db.refresh(client)
        
        logger.info(f"Updated client id={client.id}")
        return client
    
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
