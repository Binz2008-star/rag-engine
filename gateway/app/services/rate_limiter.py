import time
from typing import Optional
from app.cache.redis_client import get_redis
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class RateLimiter:
    """Token bucket rate limiter using Redis."""
    
    def __init__(
        self,
        requests: int = None,
        window: int = None,
        key_prefix: str = "rate_limit"
    ):
        self.requests = requests or settings.RATE_LIMIT_REQUESTS
        self.window = window or settings.RATE_LIMIT_WINDOW
        self.key_prefix = key_prefix
    
    def _get_key(self, identifier: str) -> str:
        """Generate Redis key for rate limiting."""
        return f"{self.key_prefix}:{identifier}"
    
    async def is_allowed(self, identifier: str) -> bool:
        """
        Check if request is allowed based on rate limit.
        
        Args:
            identifier: Unique identifier (e.g., API key, IP)
        
        Returns:
            True if allowed, False otherwise
        """
        try:
            redis = await get_redis()
            key = self._get_key(identifier)
            current_time = int(time.time())
            window_start = current_time - self.window
            
            # Remove old entries
            await redis.zremrangebyscore(key, 0, window_start)
            
            # Count current requests
            current_count = await redis.zcard(key)
            
            if current_count < self.requests:
                # Add current request
                await redis.zadd(key, {str(current_time): current_time})
                await redis.expire(key, self.window)
                logger.info("rate_limit_allowed", identifier=identifier, count=current_count + 1)
                return True
            else:
                logger.warning("rate_limit_exceeded", identifier=identifier, count=current_count)
                return False
                
        except Exception as e:
            logger.error("rate_limit_error", error=str(e), identifier=identifier)
            # Fail open - allow request if Redis fails
            return True
    
    async def get_remaining(self, identifier: str) -> int:
        """Get remaining requests in current window."""
        try:
            redis = await get_redis()
            key = self._get_key(identifier)
            current_count = await redis.zcard(key)
            return max(0, self.requests - current_count)
        except Exception as e:
            logger.error("rate_limit_remaining_error", error=str(e))
            return self.requests
