from typing import AsyncGenerator, Dict, Any
from app.providers.openai_provider import OpenAIProvider
from app.cache.cache_service import build_cache_key, get_cache, set_cache
from app.services.circuit_breaker import CircuitBreaker
from app.services.retry import retry_with_backoff
from app.core.logger import get_logger

logger = get_logger(__name__)

provider = OpenAIProvider()
circuit_breaker = CircuitBreaker(name="openai_llm")


async def generate(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Generate LLM response with caching, circuit breaker, and retry logic.
    
    Args:
        payload: Request payload for LLM
    
    Returns:
        LLM response
    """
    key = build_cache_key(payload)
    
    # Check cache first
    cached = await get_cache(key)
    if cached:
        logger.info("cache_hit", key=key[:16])
        return cached
    
    # Execute with circuit breaker and retry
    async def _execute():
        return await retry_with_backoff(provider.complete, payload)
    
    response = await circuit_breaker.call(_execute)
    
    # Cache the response
    await set_cache(key, str(response))
    
    logger.info("llm_generate_success", model=payload.get("model"))
    return response


async def stream(payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
    """
    Stream LLM response with circuit breaker protection.
    
    Args:
        payload: Request payload for LLM
    
    Yields:
        Response chunks
    """
    async def _execute():
        async for chunk in provider.stream(payload):
            yield chunk
    
    async for chunk in circuit_breaker.call(_execute):
        yield chunk
    
    logger.info("llm_stream_success", model=payload.get("model"))
