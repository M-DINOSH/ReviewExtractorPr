"""
Decorator pattern implementation for cross-cutting concerns
"""

from typing import Dict, List, Any, Callable, Optional
from functools import wraps
import asyncio
import time
import hashlib

from ..core.services import logger, event_subject


def cache_result(ttl_seconds: int = 300, key_prefix: str = ""):
    """Decorator to cache function results"""
    def decorator(func: Callable) -> Callable:
        cache = {}

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Create cache key
            key_parts = [key_prefix, func.__name__]
            key_parts.extend(str(arg) for arg in args)
            key_parts.extend(f"{k}:{v}" for k, v in sorted(kwargs.items()))
            cache_key = hashlib.md5("|".join(key_parts).encode()).hexdigest()

            # Check cache
            if cache_key in cache:
                cached_result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl_seconds:
                    logger.debug("Cache hit", function=func.__name__, key=cache_key)
                    return cached_result
                else:
                    # Remove expired entry
                    del cache[cache_key]

            # Execute function
            result = await func(*args, **kwargs)

            # Cache result
            cache[cache_key] = (result, time.time())
            logger.debug("Cache miss", function=func.__name__, key=cache_key)

            return result

        return wrapper
    return decorator


def log_execution(level: str = "info"):
    """Decorator to log function execution"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            request_id = kwargs.get('request_id', 'unknown')

            # Log start
            getattr(logger, level)("Function execution started",
                                  function=func.__name__,
                                  request_id=request_id)

            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Log success
                execution_time = time.time() - start_time
                getattr(logger, level)("Function execution completed",
                                     function=func.__name__,
                                     request_id=request_id,
                                     execution_time=execution_time)

                # Notify observers
                await event_subject.notify("function_completed", {
                    "function": func.__name__,
                    "request_id": request_id,
                    "execution_time": execution_time
                })

                return result

            except Exception as e:
                # Log error
                execution_time = time.time() - start_time
                logger.error("Function execution failed",
                           function=func.__name__,
                           request_id=request_id,
                           execution_time=execution_time,
                           error=str(e))

                # Notify observers
                await event_subject.notify("function_error", {
                    "function": func.__name__,
                    "request_id": request_id,
                    "execution_time": execution_time,
                    "error": str(e)
                })

                raise

        return wrapper
    return decorator


def rate_limit(requests_per_minute: int = 60):
    """Decorator to implement rate limiting"""
    def decorator(func: Callable) -> Callable:
        requests = {}

        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Simple in-memory rate limiting (use Redis in production)
            client_id = kwargs.get('client_id', 'anonymous')
            current_time = time.time()

            # Clean old requests
            cutoff_time = current_time - 60
            if client_id in requests:
                requests[client_id] = [
                    req_time for req_time in requests[client_id]
                    if req_time > cutoff_time
                ]

            # Check rate limit
            if client_id not in requests:
                requests[client_id] = []

            if len(requests[client_id]) >= requests_per_minute:
                logger.warning("Rate limit exceeded",
                             client_id=client_id,
                             requests_count=len(requests[client_id]))
                raise Exception(f"Rate limit exceeded: {requests_per_minute} requests per minute")

            # Add current request
            requests[client_id].append(current_time)

            # Execute function
            return await func(*args, **kwargs)

        return wrapper
    return decorator


def retry_on_failure(max_attempts: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """Decorator to retry function on failure"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            attempt = 0
            current_delay = delay

            while attempt < max_attempts:
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    attempt += 1
                    if attempt >= max_attempts:
                        logger.error("All retry attempts failed",
                                   function=func.__name__,
                                   attempts=attempt,
                                   error=str(e))
                        raise

                    logger.warning("Function failed, retrying",
                                 function=func.__name__,
                                 attempt=attempt,
                                 max_attempts=max_attempts,
                                 delay=current_delay,
                                 error=str(e))

                    await asyncio.sleep(current_delay)
                    current_delay *= backoff

        return wrapper
    return decorator


def validate_input(schema: Optional[Dict[str, Any]] = None):
    """Decorator to validate function inputs"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Basic validation - in production, use pydantic or similar
            if schema:
                for key, expected_type in schema.items():
                    if key in kwargs:
                        if not isinstance(kwargs[key], expected_type):
                            raise ValueError(f"Invalid type for {key}: expected {expected_type}, got {type(kwargs[key])}")
                    elif len(args) > 0:  # Check positional args if named not found
                        # This is simplified - real validation would be more robust
                        pass

            return await func(*args, **kwargs)

        return wrapper
    return decorator


def monitor_performance(threshold_ms: float = 1000.0):
    """Decorator to monitor function performance"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            result = await func(*args, **kwargs)
            execution_time = (time.time() - start_time) * 1000  # Convert to milliseconds

            if execution_time > threshold_ms:
                logger.warning("Slow function execution detected",
                             function=func.__name__,
                             execution_time_ms=execution_time,
                             threshold_ms=threshold_ms)

                # Notify observers
                await event_subject.notify("slow_operation", {
                    "function": func.__name__,
                    "execution_time_ms": execution_time,
                    "threshold_ms": threshold_ms
                })

            return result

        return wrapper
    return decorator</content>
<parameter name="filePath">/Users/dinoshm/Desktop/applic/ReviewExtractorPr/review-fetcher-service/app/decorators/__init__.py