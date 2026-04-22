import asyncio
import random
from typing import Callable, TypeVar, Any
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

T = TypeVar('T')


async def retry_with_backoff(
    func: Callable[..., Any],
    max_retries: int = None,
    base_delay: float = None,
    *args,
    **kwargs
) -> T:
    """
    Retry function with exponential backoff and jitter.
    
    Args:
        func: Async function to retry
        max_retries: Maximum retry attempts
        base_delay: Base delay in seconds
        *args: Function arguments
        **kwargs: Function keyword arguments
    
    Returns:
        Function result
    
    Raises:
        Exception: If all retries exhausted
    """
    max_retries = max_retries or settings.MAX_RETRIES
    base_delay = base_delay or settings.RETRY_DELAY
    
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            last_exception = e
            logger.warning(
                "retry_attempt",
                attempt=attempt,
                max_retries=max_retries,
                error=str(e)
            )
            
            if attempt < max_retries:
                # Exponential backoff with jitter
                delay = base_delay * (2 ** attempt) + random.uniform(0, 0.1)
                await asyncio.sleep(delay)
    
    logger.error("retry_exhausted", max_retries=max_retries, error=str(last_exception))
    raise last_exception
