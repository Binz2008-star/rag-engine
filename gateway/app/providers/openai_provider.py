import httpx
from typing import AsyncGenerator, Dict, Any
from app.core.config import settings
from app.core.logger import get_logger

logger = get_logger(__name__)


class OpenAIProvider:
    """OpenAI API provider with streaming support."""
    
    BASE_URL = "https://api.openai.com/v1/chat/completions"
    
    def __init__(self):
        self.api_key = settings.OPENAI_API_KEY
        self.timeout = settings.TIMEOUT
    
    async def complete(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Non-streaming completion request."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                response = await client.post(
                    self.BASE_URL,
                    json=payload,
                    headers=headers
                )
                response.raise_for_status()
                result = response.json()
                logger.info("openai_complete_success", model=payload.get("model"))
                return result
        except httpx.HTTPStatusError as e:
            logger.error("openai_http_error", status=e.response.status_code, error=str(e))
            raise
        except Exception as e:
            logger.error("openai_complete_error", error=str(e))
            raise
    
    async def stream(self, payload: Dict[str, Any]) -> AsyncGenerator[str, None]:
        """Streaming completion request."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }
        
        try:
            async with httpx.AsyncClient(timeout=None) as client:
                async with client.stream(
                    "POST",
                    self.BASE_URL,
                    json=payload,
                    headers=headers
                ) as response:
                    response.raise_for_status()
                    async for chunk in response.aiter_text():
                        if chunk:
                            yield chunk
            logger.info("openai_stream_success", model=payload.get("model"))
        except httpx.HTTPStatusError as e:
            logger.error("openai_stream_http_error", status=e.response.status_code, error=str(e))
            raise
        except Exception as e:
            logger.error("openai_stream_error", error=str(e))
            raise
