"""
Retry mechanism with exponential backoff using heapq (Priority Queue)
Implements Circuit Breaker and Bulkhead patterns
"""

import heapq
import asyncio
import time
import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Any, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class ErrorCode(str, Enum):
    """Categorize errors for different retry strategies"""
    TRANSIENT = "transient"  # 429, 5xx - should retry
    PERMANENT = "permanent"  # 401, 403, 404 - don't retry
    UNKNOWN = "unknown"


class RetryPolicy(ABC):
    """Abstract retry policy (Strategy Pattern)"""
    
    @abstractmethod
    def should_retry(self, error_code: str, attempt: int) -> bool:
        """Determine if operation should be retried"""
        pass
    
    @abstractmethod
    def get_backoff_ms(self, attempt: int) -> int:
        """Calculate backoff time for this attempt"""
        pass


class ExponentialBackoffPolicy(RetryPolicy):
    """
    Exponential backoff with jitter
    
    Formula: backoff = min(initial * multiplier^attempt, max)
    With random jitter to prevent thundering herd
    """
    
    def __init__(
        self,
        max_retries: int = 3,
        initial_backoff_ms: int = 100,
        max_backoff_ms: int = 10000,
        multiplier: float = 2.0
    ):
        self.max_retries = max_retries
        self.initial_backoff_ms = initial_backoff_ms
        self.max_backoff_ms = max_backoff_ms
        self.multiplier = multiplier
        
        # Errors that should NOT be retried
        self.permanent_errors = {"401", "403", "404", "400"}
    
    def should_retry(self, error_code: str, attempt: int) -> bool:
        """Check if error is retryable"""
        if attempt >= self.max_retries:
            return False
        
        return error_code not in self.permanent_errors
    
    def get_backoff_ms(self, attempt: int) -> int:
        """Calculate exponential backoff with jitter"""
        backoff = self.initial_backoff_ms * (self.multiplier ** attempt)
        backoff = min(backoff, self.max_backoff_ms)
        
        # Add jitter: ±10%
        import random
        jitter = backoff * 0.1 * (random.random() * 2 - 1)
        backoff = max(1, backoff + jitter)
        
        return int(backoff)


@dataclass(order=True)
class RetryTask:
    """Comparable task for heapq priority queue"""
    retry_at: float = field(compare=True)  # Unix timestamp
    attempt: int = 0
    message_id: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    error: Optional[str] = None


class RetryScheduler:
    """
    Manages retry scheduling using a priority queue (heapq)
    
    Single thread processes items in order of scheduled time.
    Implements Bulkhead pattern by isolating retry logic.
    """
    
    def __init__(
        self,
        policy: Optional[RetryPolicy] = None,
        dlq_callback: Optional[Callable] = None
    ):
        self.policy = policy or ExponentialBackoffPolicy()
        self.dlq_callback = dlq_callback
        
        self.retry_queue: list[RetryTask] = []
        self._running = False
        self._lock = asyncio.Lock()
        self._items_being_retried: Set[str] = set()
    
    async def schedule_retry(
        self,
        message_id: str,
        payload: dict[str, Any],
        error_code: str,
        attempt: int = 0
    ) -> bool:
        """
        Schedule a message for retry
        
        Args:
            message_id: Unique identifier for this message
            payload: Message content
            error_code: Error that triggered retry
            attempt: Current attempt number (0-indexed)
            
        Returns:
            True if scheduled for retry, False if should go to DLQ
        """
        if not self.policy.should_retry(error_code, attempt):
            logger.warning(
                "message_not_retryable",
                message_id=message_id,
                error_code=error_code,
                attempt=attempt
            )
            
            # Send to DLQ
            if self.dlq_callback:
                await self.dlq_callback(message_id, payload, error_code, attempt)
            return False
        
        backoff_ms = self.policy.get_backoff_ms(attempt)
        retry_at = time.time() + (backoff_ms / 1000.0)
        
        task = RetryTask(
            retry_at=retry_at,
            attempt=attempt + 1,
            message_id=message_id,
            payload=payload,
            error=error_code
        )
        
        async with self._lock:
            heapq.heappush(self.retry_queue, task)
            logger.info(
                "message_scheduled_for_retry",
                message_id=message_id,
                attempt=task.attempt,
                backoff_ms=backoff_ms,
                retry_at=retry_at
            )
        
        return True
    
    async def get_ready_tasks(self) -> list[RetryTask]:
        """Get all tasks ready for immediate retry"""
        now = time.time()
        ready = []
        
        async with self._lock:
            while self.retry_queue and self.retry_queue[0].retry_at <= now:
                task = heapq.heappop(self.retry_queue)
                ready.append(task)
        
        return ready
    
    async def is_being_retried(self, message_id: str) -> bool:
        """Check if message is currently being retried"""
        async with self._lock:
            return message_id in self._items_being_retried
    
    async def mark_retry_start(self, message_id: str) -> None:
        """Mark message as being processed"""
        async with self._lock:
            self._items_being_retried.add(message_id)
    
    async def mark_retry_end(self, message_id: str) -> None:
        """Mark message as done processing"""
        async with self._lock:
            self._items_being_retried.discard(message_id)
    
    def get_queue_size(self) -> int:
        """Get current queue size"""
        return len(self.retry_queue)
    
    def clear(self) -> None:
        """Clear all pending retries"""
        self.retry_queue.clear()


class CircuitBreaker:
    """
    Circuit Breaker pattern to prevent cascading failures
    
    States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing) -> CLOSED
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        timeout_sec: int = 60
    ):
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.timeout_sec = timeout_sec
        
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
    
    def record_success(self) -> None:
        """Record successful operation"""
        self.failure_count = 0
        
        if self.state == "HALF_OPEN":
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                self.state = "CLOSED"
                self.success_count = 0
                logger.info("circuit_breaker_closed")
    
    def record_failure(self) -> None:
        """Record failed operation"""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.success_count = 0
        
        if self.failure_count >= self.failure_threshold:
            if self.state == "CLOSED":
                self.state = "OPEN"
                logger.warning(f"circuit_breaker_opened")
    
    def can_execute(self) -> bool:
        """Check if operation can execute"""
        if self.state == "CLOSED":
            return True
        
        if self.state == "OPEN":
            # Check if timeout elapsed
            if self.last_failure_time and \
               (time.time() - self.last_failure_time) >= self.timeout_sec:
                self.state = "HALF_OPEN"
                self.success_count = 0
                logger.info("circuit_breaker_half_open")
                return True
            return False
        
        # HALF_OPEN - allow operation
        return True
    
    def get_state(self) -> str:
        """Get current state"""
        return self.state
