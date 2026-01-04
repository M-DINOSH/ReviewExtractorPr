"""
Core abstractions and interfaces following SOLID principles

This module defines the fundamental interfaces and abstract base classes
that provide the foundation for the scalable, modular microservice architecture.
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional, Protocol
from dataclasses import dataclass
from enum import Enum
import asyncio
from contextlib import asynccontextmanager


class ServiceStatus(Enum):
    """Service operational status"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


@dataclass
class ServiceHealth:
    """Service health information"""
    status: ServiceStatus
    name: str
    version: str
    uptime: float
    metrics: Dict[str, Any]


class IService(Protocol):
    """Core service interface - Interface Segregation Principle"""

    @abstractmethod
    async def get_health(self) -> ServiceHealth:
        """Get service health status"""
        pass

    @abstractmethod
    async def shutdown(self) -> None:
        """Gracefully shutdown the service"""
        pass


class IDataProvider(ABC):
    """Data provider interface - Dependency Inversion Principle"""

    @abstractmethod
    async def get_accounts(self, access_token: str) -> List[Dict[str, Any]]:
        """Get all accounts accessible with the access token"""
        pass

    @abstractmethod
    async def get_locations(self, account_id: str) -> List[Dict[str, Any]]:
        """Get all locations for a specific account"""
        pass

    @abstractmethod
    async def get_reviews(self, location_id: str) -> List[Dict[str, Any]]:
        """Get all reviews for a specific location"""
        pass


class ISyncService(ABC):
    """Sync service interface - Single Responsibility Principle"""

    @abstractmethod
    async def sync_reviews(self, access_token: str) -> Dict[str, Any]:
        """Execute the complete sync flow and return combined JSON"""
        pass


class IRepository(ABC):
    """Repository interface for data access - Repository Pattern"""

    @abstractmethod
    async def save(self, entity: Any) -> None:
        """Save an entity"""
        pass

    @abstractmethod
    async def find_by_id(self, entity_id: Any) -> Optional[Any]:
        """Find entity by ID"""
        pass

    @abstractmethod
    async def find_all(self, **filters) -> List[Any]:
        """Find all entities matching filters"""
        pass


class ICache(ABC):
    """Cache interface - Strategy Pattern"""

    @abstractmethod
    async def get(self, key: str) -> Optional[Any]:
        """Get value from cache"""
        pass

    @abstractmethod
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set value in cache with optional TTL"""
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """Delete value from cache"""
        pass


class IQueue(ABC):
    """Queue interface for request queuing - Strategy Pattern"""

    @abstractmethod
    async def enqueue(self, item: Any) -> None:
        """Add item to queue"""
        pass

    @abstractmethod
    async def dequeue(self) -> Optional[Any]:
        """Remove and return item from queue"""
        pass

    @abstractmethod
    async def size(self) -> int:
        """Get queue size"""
        pass

    @abstractmethod
    async def is_empty(self) -> bool:
        """Check if queue is empty"""
        pass


class ILogger(ABC):
    """Logger interface - Strategy Pattern"""

    @abstractmethod
    def info(self, message: str, **kwargs) -> None:
        """Log info message"""
        pass

    @abstractmethod
    def error(self, message: str, **kwargs) -> None:
        """Log error message"""
        pass

    @abstractmethod
    def warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        pass

    @abstractmethod
    def debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        pass


class IObserver(ABC):
    """Observer interface - Observer Pattern"""

    @abstractmethod
    async def update(self, event: str, data: Dict[str, Any]) -> None:
        """Handle event notification"""
        pass


class ISubject(ABC):
    """Subject interface - Observer Pattern"""

    @abstractmethod
    def attach(self, observer: IObserver) -> None:
        """Attach an observer"""
        pass

    @abstractmethod
    def detach(self, observer: IObserver) -> None:
        """Detach an observer"""
        pass

    @abstractmethod
    async def notify(self, event: str, data: Dict[str, Any]) -> None:
        """Notify all observers of an event"""
        pass


class ICommand(ABC):
    """Command interface - Command Pattern"""

    @abstractmethod
    async def execute(self) -> Any:
        """Execute the command"""
        pass

    @abstractmethod
    def get_name(self) -> str:
        """Get command name"""
        pass


class IFactory(ABC):
    """Factory interface - Factory Pattern"""

    @abstractmethod
    def create_service(self, service_type: str, **kwargs) -> IService:
        """Create a service instance"""
        pass


@asynccontextmanager
async def service_lifecycle(service: IService):
    """Context manager for service lifecycle management"""
    try:
        yield service
    finally:
        # Note: shutdown should be called by the service manager
        pass

