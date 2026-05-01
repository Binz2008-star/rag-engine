"""OpenAI-compatible client for Ollama and compatible providers.

Production-grade implementation with:
- Structured error handling
- Environment-based configuration
- Retry logic with exponential backoff
- Type hints
- Request/response logging
"""

from __future__ import annotations

import logging
import os
import time
from typing import Any, Optional

from openai import OpenAI, APIError, APIConnectionError, RateLimitError
from pydantic import BaseModel, Field

from app.config import MAX_RETRIES, TIMEOUT

logger = logging.getLogger(__name__)


class ChatMessage(BaseModel):
    """Structured chat message with role and content."""

    role: str = Field(..., description="Message role: system, user, assistant")
    content: str | list[dict[str, Any]] = Field(..., description="Message content")


class GenerationParams(BaseModel):
    """Inference parameters for generation."""

    max_tokens: int = 2048
    temperature: float = 0.8
    top_p: float = 0.1
    frequency_penalty: float = 0.0
    presence_penalty: float = 0.0


class OpenAICompatibleClient:
    """OpenAI-compatible client for Ollama and similar providers."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        model: Optional[str] = None,
        timeout: int = TIMEOUT,
        max_retries: int = MAX_RETRIES,
    ) -> None:
        """Initialize client with environment-based defaults.

        Args:
            base_url: Provider base URL (default: OLLAMA_BASE_URL env var or localhost:11434/v1)
            api_key: API key (default: OPENAI_API_KEY env var or "unused")
            model: Model name (default: CHAT_MODEL env var)
            timeout: Request timeout in seconds
            max_retries: Maximum retry attempts on failure
        """
        self.base_url = base_url or os.getenv(
            "OLLAMA_BASE_URL", "http://127.0.0.1:11434/v1"
        )
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "unused")
        self.model = model or os.getenv("CHAT_MODEL", "qwen3:8b")
        self.timeout = timeout
        self.max_retries = max_retries

        self.client = OpenAI(
            base_url=self.base_url,
            api_key=self.api_key,
            timeout=timeout,
        )

        logger.info(
            f"Initialized OpenAI-compatible client: base_url={self.base_url}, model={self.model}"
        )

    def generate(
        self,
        messages: list[ChatMessage],
        params: Optional[GenerationParams] = None,
    ) -> str:
        """Generate response from chat messages.

        Args:
            messages: List of chat messages
            params: Generation parameters (uses defaults if None)

        Returns:
            Generated text response

        Raises:
            APIError: If all retry attempts fail
        """
        if params is None:
            params = GenerationParams()

        message_dicts = [msg.model_dump() for msg in messages]

        last_exception: Optional[Exception] = None

        for attempt in range(self.max_retries):
            try:
                logger.debug(
                    f"Generation attempt {attempt + 1}/{self.max_retries} "
                    f"with model={self.model}"
                )

                response = self.client.chat.completions.create(
                    messages=message_dicts,
                    model=self.model,
                    max_tokens=params.max_tokens,
                    temperature=params.temperature,
                    top_p=params.top_p,
                    frequency_penalty=params.frequency_penalty,
                    presence_penalty=params.presence_penalty,
                )

                result = response.choices[0].message.content
                logger.debug(f"Generation successful, tokens={response.usage.total_tokens}")
                return result or ""

            except RateLimitError as exc:
                last_exception = exc
                logger.warning(f"Rate limit hit on attempt {attempt + 1}: {exc}")
                backoff = min(2**attempt, 60)  # Cap at 60s
                time.sleep(backoff)

            except APIConnectionError as exc:
                last_exception = exc
                logger.warning(f"Connection error on attempt {attempt + 1}: {exc}")
                backoff = min(2**attempt, 30)  # Cap at 30s
                time.sleep(backoff)

            except APIError as exc:
                last_exception = exc
                logger.error(f"API error on attempt {attempt + 1}: {exc}")
                # Don't retry on API errors (4xx, 5xx from provider)
                break

            except Exception as exc:
                last_exception = exc
                logger.error(f"Unexpected error on attempt {attempt + 1}: {exc}")
                backoff = min(2**attempt, 10)  # Cap at 10s
                time.sleep(backoff)

        # All retries exhausted
        error_msg = f"Generation failed after {self.max_retries} attempts"
        if last_exception:
            error_msg += f": {last_exception}"
        logger.error(error_msg)
        raise APIError(error_msg) from last_exception

    def generate_simple(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        params: Optional[GenerationParams] = None,
    ) -> str:
        """Generate response from a simple text prompt.

        Args:
            prompt: User prompt text
            system_prompt: Optional system instruction
            params: Generation parameters

        Returns:
            Generated text response
        """
        messages: list[ChatMessage] = []

        if system_prompt:
            messages.append(ChatMessage(role="system", content=system_prompt))

        messages.append(ChatMessage(role="user", content=prompt))

        return self.generate(messages, params)

    def health_check(self) -> bool:
        """Check if the provider is accessible.

        Returns:
            True if provider responds to a minimal request
        """
        try:
            self.client.models.list()
            return True
        except Exception as exc:
            logger.warning(f"Health check failed: {exc}")
            return False


# Convenience function for quick usage
def create_client(
    base_url: Optional[str] = None,
    model: Optional[str] = None,
) -> OpenAICompatibleClient:
    """Factory function to create a configured client.

    Args:
        base_url: Override base URL from environment
        model: Override model from environment

    Returns:
        Configured OpenAI-compatible client
    """
    return OpenAICompatibleClient(base_url=base_url, model=model)
