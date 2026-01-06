"""
Bounded deque (double-ended queue) for burst smoothing
Implements Adapter pattern to wrap collections.deque
"""

from collections import deque
from typing import Any, Optional
import asyncio
import logging

logger = logging.getLogger(__name__)


class BoundedDequeBuffer:
    """
    Thread-safe bounded deque for job buffering
    
    Design: Adapter pattern wrapping collections.deque
    - Provides fixed-size buffer (FIFO)
    - Rejects new items if full (returns False)
    - Used by API to queue jobs for async processing
    
    Returns HTTP 429 (Too Many Requests) when full,
    encouraging client backoff.
    """
    
    def __init__(self, max_size: int = 10000):
        """
        Args:
            max_size: Maximum items before rejecting new items
        """
        self.max_size = max_size
        self._queue: deque[Any] = deque(maxlen=max_size)
        self._lock = asyncio.Lock()
        self._metrics = {
            "enqueued": 0,
            "dequeued": 0,
            "rejected": 0,
            "max_size_hit": 0
        }
    
    async def enqueue(self, item: Any) -> bool:
        """
        Add item to queue
        
        Args:
            item: Item to enqueue
            
        Returns:
            True if enqueued, False if queue is full
        """
        async with self._lock:
            if len(self._queue) >= self.max_size:
                self._metrics["rejected"] += 1
                self._metrics["max_size_hit"] += 1
                logger.warning(
                    "deque_full queue_size=%s max_size=%s",
                    len(self._queue),
                    self.max_size,
                )
                return False
            
            try:
                self._queue.append(item)
                self._metrics["enqueued"] += 1
                logger.debug("item_enqueued queue_size=%s", len(self._queue))
                return True
            except Exception as e:
                logger.error("enqueue_error %s", str(e))
                return False
    
    async def dequeue(self) -> Optional[Any]:
        """
        Remove and return item from queue (FIFO order)
        
        Returns:
            Item from queue or None if empty
        """
        async with self._lock:
            if not self._queue:
                return None
            
            try:
                item = self._queue.popleft()
                self._metrics["dequeued"] += 1
                return item
            except IndexError:
                return None
    
    async def dequeue_batch(self, batch_size: int = 100) -> list[Any]:
        """
        Dequeue multiple items at once
        
        Args:
            batch_size: Maximum items to dequeue
            
        Returns:
            List of items (may be smaller than batch_size)
        """
        batch = []
        async with self._lock:
            for _ in range(min(batch_size, len(self._queue))):
                try:
                    batch.append(self._queue.popleft())
                    self._metrics["dequeued"] += 1
                except IndexError:
                    break
        
        return batch
    
    async def size(self) -> int:
        """Get current queue size"""
        async with self._lock:
            return len(self._queue)
    
    async def is_full(self) -> bool:
        """Check if queue is at max capacity"""
        async with self._lock:
            return len(self._queue) >= self.max_size
    
    async def is_empty(self) -> bool:
        """Check if queue is empty"""
        async with self._lock:
            return len(self._queue) == 0
    
    async def get_load_percent(self) -> float:
        """Get queue utilization percentage"""
        async with self._lock:
            return (len(self._queue) / self.max_size) * 100.0
    
    async def clear(self) -> None:
        """Clear all items from queue"""
        async with self._lock:
            self._queue.clear()
            logger.info("deque_cleared")
    
    def get_metrics(self) -> dict:
        """Get queue metrics"""
        return {
            **self._metrics,
            "current_size": len(self._queue),
            "max_size": self.max_size
        }
    
    def reset_metrics(self) -> None:
        """Reset metrics counters"""
        self._metrics = {
            "enqueued": 0,
            "dequeued": 0,
            "rejected": 0,
            "max_size_hit": 0
        }
