"""
LLM Retry Utilities

Provides retry logic for LLM API calls that may experience transient failures.
Handles OpenAI, OpenRouter, and other OpenAI-compatible API errors.
"""
import asyncio
from functools import wraps
from typing import TypeVar, Callable, Any, Optional
from loguru import logger

T = TypeVar('T')

# Transient error codes that should be retried
RETRYABLE_STATUS_CODES = {
    500,  # Internal Server Error
    502,  # Bad Gateway
    503,  # Service Unavailable
    504,  # Gateway Timeout
    429,  # Rate Limited (with backoff)
}


def is_retryable_error(error: Exception) -> bool:
    """Check if an error is transient and should be retried."""
    error_str = str(error).lower()
    error_type = type(error).__name__
    
    # Check for known retryable error types
    if "internalservererror" in error_type.lower():
        return True
    if "serviceunavailable" in error_type.lower():
        return True
    if "ratelimit" in error_type.lower():
        return True
    if "timeout" in error_type.lower():
        return True
    if "connection" in error_type.lower():
        return True
    
    # Check error message for status codes
    for code in RETRYABLE_STATUS_CODES:
        if f"error code: {code}" in error_str or f"status code {code}" in error_str:
            return True
    
    # Check for common transient error messages
    transient_patterns = [
        "internal server error",
        "service unavailable",
        "bad gateway",
        "gateway timeout",
        "rate limit",
        "too many requests",
        "connection reset",
        "connection refused",
        "temporarily unavailable",
        "overloaded",
    ]
    
    for pattern in transient_patterns:
        if pattern in error_str:
            return True
    
    return False


def retry_llm_operation(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exponential_base: float = 2.0,
):
    """
    Decorator to retry async LLM operations with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay between retries (seconds)
        max_delay: Maximum delay between retries (seconds)
        exponential_base: Base for exponential backoff
    
    Usage:
        @retry_llm_operation(max_retries=3)
        async def call_llm():
            return await llm.ainvoke(messages)
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs) -> T:
            last_error: Optional[Exception] = None
            
            for attempt in range(max_retries + 1):  # +1 for initial attempt
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_error = e
                    
                    if not is_retryable_error(e):
                        # Non-retryable error, fail immediately
                        logger.error(f"LLM operation {func.__name__} failed with non-retryable error: {e}")
                        raise
                    
                    if attempt == max_retries:
                        # Final attempt failed
                        logger.error(
                            f"LLM operation {func.__name__} failed after {max_retries + 1} attempts: {e}"
                        )
                        raise
                    
                    # Calculate delay with exponential backoff
                    delay = min(base_delay * (exponential_base ** attempt), max_delay)
                    
                    logger.warning(
                        f"LLM operation {func.__name__} failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                        f"Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
            
            # Should never reach here, but just in case
            if last_error:
                raise last_error
            raise RuntimeError(f"LLM operation {func.__name__} failed unexpectedly")
        
        return wrapper
    return decorator


async def invoke_with_retry(
    llm_callable: Callable,
    *args,
    max_retries: int = 3,
    base_delay: float = 1.0,
    **kwargs
) -> Any:
    """
    Invoke an LLM callable with retry logic.
    
    This is a function-based alternative to the decorator for one-off calls.
    
    Usage:
        result = await invoke_with_retry(llm.ainvoke, messages, max_retries=3)
    """
    last_error: Optional[Exception] = None
    
    for attempt in range(max_retries + 1):
        try:
            return await llm_callable(*args, **kwargs)
        except Exception as e:
            last_error = e
            
            if not is_retryable_error(e):
                logger.error(f"LLM call failed with non-retryable error: {e}")
                raise
            
            if attempt == max_retries:
                logger.error(f"LLM call failed after {max_retries + 1} attempts: {e}")
                raise
            
            delay = min(base_delay * (2 ** attempt), 30.0)
            logger.warning(
                f"LLM call failed (attempt {attempt + 1}/{max_retries + 1}): {e}. "
                f"Retrying in {delay:.1f}s..."
            )
            await asyncio.sleep(delay)
    
    if last_error:
        raise last_error
    raise RuntimeError("LLM call failed unexpectedly")
