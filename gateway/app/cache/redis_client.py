import redis.asyncio as redis
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

redis_client = redis.from_url(
    settings.REDIS_URL,
    decode_responses=True,
    socket_timeout=5,
    socket_connect_timeout=5
)


async def get_redis():
    """Get Redis client instance."""
    return redis_client


async def close_redis():
    """Close Redis connection."""
    await redis_client.close()
