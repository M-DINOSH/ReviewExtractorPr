"""
Token Bucket rate limiter implementation
Follows Strategy pattern for rate limiting algorithms
"""

import asyncio
import time
from abc import ABC, abstractmethod
from typing import Dict
from dataclasses import dataclass
from datetime import datetime
import logging
import structlog

logger = structlog.get_logger()


@dataclass
class TokenBucketState:
    """State of a single token bucket"""
    capacity: float
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float  # timestamp


class RateLimiter(ABC):
    """Abstract base class for rate limiting strategies (Strategy Pattern)"""
    
    @abstractmethod
    async def acquire(self, tokens: int = 1) -> bool:
        """Try to acquire tokens. Returns True if successful"""
        pass
    
    @abstractmethod
    def get_available_tokens(self) -> float:
        """Get currently available tokens"""
        pass


class TokenBucketLimiter(RateLimiter):
    """
    Token Bucket algorithm implementation
    
    Algorithm:
    - Each bucket has capacity C and refill rate R (tokens/sec)
    - On acquire request: check if tokens >= requested
    - If yes: decrement and return True
    - If no: return False (caller must retry)
    - Background: tokens refill at rate R per second
    """
    
    def __init__(
        self,
        capacity: float,
        refill_rate: float
    ):
        """
        Args:
            capacity: Maximum tokens in bucket
            refill_rate: Tokens per second to refill
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = capacity
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()
    
    async def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens from bucket
        
        Returns:
            True if tokens acquired, False if insufficient
        """
        async with self._lock:
            self._refill()
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                logger.debug(
                    f"acquired_tokens",
                    tokens=tokens,
                    remaining=self.tokens
                )
                return True
            
            logger.debug(
                f"insufficient_tokens",
                requested=tokens,
                available=self.tokens
            )
            return False
    
    async def acquire_blocking(self, tokens: int = 1, timeout_sec: float = 30.0) -> bool:
        """
        Blocking acquire with timeout
        
        Args:
            tokens: Number of tokens to acquire
            timeout_sec: Maximum wait time
            
        Returns:
            True if acquired, False if timeout
        """
        start = time.monotonic()
        
        while True:
            if await self.acquire(tokens):
                return True
            
            elapsed = time.monotonic() - start
            if elapsed >= timeout_sec:
                logger.warning(
                    "rate_limit_timeout",
                    tokens=tokens,
                    timeout=timeout_sec
                )
                return False
            
            # Wait small amount before retrying
            await asyncio.sleep(0.01)
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time (not async for efficiency)"""
        now = time.monotonic()
        elapsed = now - self.last_refill
        
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def get_available_tokens(self) -> float:
        """Get current token count without acquiring"""
        self._refill()
        return self.tokens
    
    def reset(self) -> None:
        """Reset bucket to full capacity"""
        self.tokens = self.capacity
        self.last_refill = time.monotonic()


class PerWorkerRateLimiter:
    """
    Manages rate limiters per worker ID
    Useful for per-account or per-location rate limiting
    """
    
    def __init__(self, capacity: float, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.limiters: Dict[str, TokenBucketLimiter] = {}
        self._lock = asyncio.Lock()
    
    async def acquire(self, worker_id: str, tokens: int = 1) -> bool:
        """Acquire tokens for specific worker"""
        async with self._lock:
            if worker_id not in self.limiters:
                self.limiters[worker_id] = TokenBucketLimiter(
                    self.capacity, 
                    self.refill_rate
                )
        
        limiter = self.limiters[worker_id]
        return await limiter.acquire(tokens)
    
    def get_limiter(self, worker_id: str) -> TokenBucketLimiter:
        """Get or create limiter for worker"""
        if worker_id not in self.limiters:
            self.limiters[worker_id] = TokenBucketLimiter(
                self.capacity, 
                self.refill_rate
            )
        return self.limiters[worker_id]
    
    def cleanup_stale_limiters(self, max_idle_sec: float = 3600) -> int:
        """
        Remove limiters that haven't been used recently
        
        Args:
            max_idle_sec: Remove if not used in this many seconds
            
        Returns:
            Number of limiters removed
        """
        now = time.monotonic()
        to_remove = []
        
        for worker_id, limiter in self.limiters.items():
            idle_time = now - limiter.last_refill
            if idle_time > max_idle_sec:
                to_remove.append(worker_id)
        
        for worker_id in to_remove:
            del self.limiters[worker_id]
        
        if to_remove:
            logger.info("cleaned_up_limiters count=%d", len(to_remove))
        
        return len(to_remove)
