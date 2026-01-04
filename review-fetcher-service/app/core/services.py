"""
Core service implementations following SOLID principles and design patterns
"""

from typing import Dict, List, Any, Optional, Type
import asyncio
import time
from collections import deque
import structlog

from .interfaces import (
    IService, ServiceStatus, ServiceHealth, IQueue, ICache,
    ILogger, IObserver, ISubject, ICommand, IFactory
)


class BaseService(IService):
    """Base service class implementing common functionality"""

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self.start_time = time.time()
        self._observers: List[IObserver] = []

    async def get_health(self) -> ServiceHealth:
        """Get service health status"""
        uptime = time.time() - self.start_time
        return ServiceHealth(
            status=ServiceStatus.HEALTHY,
            name=self.name,
            version=self.version,
            uptime=uptime,
            metrics={}
        )

    async def shutdown(self) -> None:
        """Gracefully shutdown the service"""
        await self._notify_observers("shutdown", {"service": self.name})

    async def _notify_observers(self, event: str, data: Dict[str, Any]) -> None:
        """Notify all observers of an event"""
        for observer in self._observers:
            try:
                await observer.update(event, data)
            except Exception as e:
                # Don't let observer errors crash the service
                print(f"Observer error: {e}")


class DequeQueue(IQueue):
    """Thread-safe deque-based queue implementation"""

    def __init__(self, max_size: int = 1000):
        self._queue = deque()
        self._lock = asyncio.Lock()
        self._max_size = max_size

    async def enqueue(self, item: Any) -> None:
        """Add item to queue"""
        async with self._lock:
            if len(self._queue) >= self._max_size:
                raise OverflowError("Queue is full")
            self._queue.append(item)

    async def dequeue(self) -> Optional[Any]:
        """Remove and return item from queue"""
        async with self._lock:
            return self._queue.popleft() if self._queue else None

    async def size(self) -> int:
        """Get queue size"""
        async with self._lock:
            return len(self._queue)

    async def is_empty(self) -> bool:
        """Check if queue is empty"""
        async with self._lock:
            return len(self._queue) == 0


class StructlogLogger(ILogger):
    """Structlog-based logger implementation"""

    def __init__(self):
        self._logger = structlog.get_logger()

    def info(self, message: str, **kwargs) -> None:
        """Log info message"""
        self._logger.info(message, **kwargs)

    def error(self, message: str, **kwargs) -> None:
        """Log error message"""
        self._logger.error(message, **kwargs)

    def warning(self, message: str, **kwargs) -> None:
        """Log warning message"""
        self._logger.warning(message, **kwargs)

    def debug(self, message: str, **kwargs) -> None:
        """Log debug message"""
        self._logger.debug(message, **kwargs)


class EventSubject(ISubject):
    """Observable subject for event notifications"""

    def __init__(self):
        self._observers: List[IObserver] = []

    def attach(self, observer: IObserver) -> None:
        """Attach an observer"""
        if observer not in self._observers:
            self._observers.append(observer)

    def detach(self, observer: IObserver) -> None:
        """Detach an observer"""
        try:
            self._observers.remove(observer)
        except ValueError:
            pass

    async def notify(self, event: str, data: Dict[str, Any]) -> None:
        """Notify all observers of an event"""
        tasks = []
        for observer in self._observers:
            tasks.append(observer.update(event, data))
        await asyncio.gather(*tasks, return_exceptions=True)


class ServiceFactory(IFactory):
    """Factory for creating service instances"""

    def __init__(self):
        self._service_registry: Dict[str, Type[IService]] = {}

    def register_service(self, service_type: str, service_class: Type[IService]) -> None:
        """Register a service class"""
        self._service_registry[service_type] = service_class

    def create_service(self, service_type: str, **kwargs) -> IService:
        """Create a service instance"""
        service_class = self._service_registry.get(service_type)
        if not service_class:
            raise ValueError(f"Unknown service type: {service_type}")
        return service_class(**kwargs)


# Global instances
service_factory = ServiceFactory()

# Global instances
service_factory = ServiceFactory()
logger = StructlogLogger()
event_subject = EventSubject()
