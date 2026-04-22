import time
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.responses import StreamingResponse
from typing import Dict, Any
from app.schemas.requests import ChatCompletionRequest, RateLimitCheck
from app.schemas.responses import ChatCompletionResponse, ErrorResponse, RateLimitResponse
from app.services.llm_service import generate, stream
from app.services.rate_limiter import RateLimiter
from app.services.metrics import record_request, record_cache_hit, record_error
from app.cache.redis_client import get_redis
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)

router = APIRouter()
rate_limiter = RateLimiter()


def get_client_identifier(request: Request) -> str:
    """Extract client identifier from request."""
    # Try API key first, then fallback to IP
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"api_key:{api_key}"
    
    # Fallback to client IP
    client_host = request.client.host if request.client else "unknown"
    return f"ip:{client_host}"


@router.get("/health")
async def health_check():
    """Health check endpoint."""
    try:
        redis = await get_redis()
        await redis.ping()
        redis_connected = True
    except Exception:
        redis_connected = False
    
    from datetime import datetime
    from app.schemas.responses import HealthResponse
    
    return HealthResponse(
        status="healthy" if redis_connected else "degraded",
        version=settings.VERSION,
        redis_connected=redis_connected,
        timestamp=datetime.utcnow()
    )


@router.post("/rate-limit/check")
async def check_rate_limit(check: RateLimitCheck):
    """Check rate limit status for an identifier."""
    allowed = await rate_limiter.is_allowed(check.identifier)
    remaining = await rate_limiter.get_remaining(check.identifier)
    
    return RateLimitResponse(
        allowed=allowed,
        remaining=remaining
    )


@router.post("/generate")
async def generate_completion(
    request: ChatCompletionRequest,
    http_request: Request
):
    """
    Generate non-streaming LLM completion.
    
    Rate limited, cached, and monitored.
    """
    identifier = get_client_identifier(http_request)
    
    # Rate limit check
    if not await rate_limiter.is_allowed(identifier):
        logger.warning("rate_limit_exceeded", identifier=identifier)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    start_time = time.time()
    
    try:
        payload = request.model_dump()
        
        # Record metrics
        record_request(model=payload.get("model"), method="generate")
        
        # Generate response
        response = await generate(payload)
        
        duration = time.time() - start_time
        logger.info(
            "generate_success",
            model=payload.get("model"),
            duration=duration,
            identifier=identifier
        )
        
        return response
        
    except Exception as e:
        duration = time.time() - start_time
        record_error(model=request.model, error_type=type(e).__name__)
        logger.error(
            "generate_error",
            error=str(e),
            model=request.model,
            duration=duration,
            identifier=identifier
        )
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/stream")
async def stream_completion(
    request: ChatCompletionRequest,
    http_request: Request
):
    """
    Generate streaming LLM completion.
    
    Rate limited and monitored.
    """
    identifier = get_client_identifier(http_request)
    
    # Rate limit check
    if not await rate_limiter.is_allowed(identifier):
        logger.warning("rate_limit_exceeded", identifier=identifier)
        raise HTTPException(status_code=429, detail="Rate limit exceeded")
    
    try:
        payload = request.model_dump()
        payload["stream"] = True
        
        # Record metrics
        record_request(model=payload.get("model"), method="stream")
        
        logger.info("stream_start", model=payload.get("model"), identifier=identifier)
        
        return StreamingResponse(
            stream(payload),
            media_type="text/event-stream"
        )
        
    except Exception as e:
        record_error(model=request.model, error_type=type(e).__name__)
        logger.error(
            "stream_error",
            error=str(e),
            model=request.model,
            identifier=identifier
        )
        raise HTTPException(status_code=500, detail=str(e))
