import hashlib
import json
from typing import Optional, Any
from app.cache.redis_client import get_redis
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


def build_cache_key(payload: dict) -> str:
    """Build deterministic cache key from payload."""
    raw = json.dumps(payload, sort_keys=True)
    hash_digest = hashlib.sha256(raw.encode()).hexdigest()
    return f"llm:{hash_digest}"


async def get_cache(key: str) -> Optional[str]:
    """Retrieve value from cache."""
    try:
        redis = await get_redis()
        value = await redis.get(key)
        if value:
            logger.info("cache_hit", key=key)
        return value
    except Exception as e:
        logger.error("cache_get_error", error=str(e), key=key)
        return None


async def set_cache(key: str, value: str, ttl: Optional[int] = None) -> bool:
    """Store value in cache with TTL."""
    try:
        redis = await get_redis()
        await redis.set(key, value, ex=ttl or settings.CACHE_TTL)
        logger.info("cache_set", key=key, ttl=ttl or settings.CACHE_TTL)
        return True
    except Exception as e:
        logger.error("cache_set_error", error=str(e), key=key)
        return False


async def delete_cache(key: str) -> bool:
    """Delete value from cache."""
    try:
        redis = await get_redis()
        await redis.delete(key)
        logger.info("cache_delete", key=key)
        return True
    except Exception as e:
        logger.error("cache_delete_error", error=str(e), key=key)
        return False
