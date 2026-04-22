from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass
from typing import Any

import requests

from ..core.config import get_settings

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeneralChatResponse:
    capability: str
    intent: str
    answer: str
    status: str


class GeneralChatService:
    def __init__(self, base_url: str | None = None, model: str | None = None) -> None:
        settings = get_settings()
        self._base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self._model = model or settings.chat_model
        self._timeout = 30
        self._max_retries = 3

    def _call_ollama(self, prompt: str) -> str:
        """Minimal Ollama client for non-RAG general chat."""
        system_prompt = (
            "You are a helpful AI assistant. Answer questions naturally and helpfully.\n"
            "Guidelines:\n"
            "- If unsure about something, say so plainly\n"
            "- Do not claim access to private documents or specific knowledge bases\n"
            "- For greetings, help requests, and general questions, respond conversationally\n"
            "- Keep answers concise but informative\n"
            "- Do not use phrases like 'Insufficient data.' for normal conversation"
        )

        last_exc: Exception | None = None

        for attempt in range(self._max_retries):
            try:
                response = requests.post(
                    f"{self._base_url}/api/chat",
                    json={
                        "model": self._model,
                        "stream": False,
                        "messages": [
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": prompt},
                        ],
                        "options": {
                            "temperature": 0.7,
                            "top_k": 40,
                            "top_p": 0.9,
                            "num_ctx": 2048,
                            "num_predict": 512,
                        },
                    },
                    timeout=self._timeout,
                )
                response.raise_for_status()

                payload = response.json()
                text = payload["message"]["content"].strip()
                return text

            except requests.exceptions.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "General chat LLM request failed on attempt %d/%d: %r",
                    attempt + 1,
                    self._max_retries,
                    exc,
                )
                if attempt < self._max_retries - 1:
                    time.sleep(2**attempt)
            except (KeyError, ValueError, TypeError) as exc:
                last_exc = exc
                logger.error("Invalid Ollama response payload: %r", exc)
                break

        logger.error("General chat LLM generation failed after %d attempts: %r", self._max_retries, last_exc)
        raise RuntimeError(f"General chat LLM generation failed: {last_exc!r}")

    async def chat(self, question: str) -> GeneralChatResponse:
        """Process a general chat question without retrieval."""
        if not question or not question.strip():
            return GeneralChatResponse(
                capability="general",
                intent="chat",
                answer="Please provide a question or message.",
                status="error",
            )

        try:
            answer = await asyncio.to_thread(self._call_ollama, question.strip())
            return GeneralChatResponse(
                capability="general",
                intent="chat",
                answer=answer,
                status="ok",
            )
        except Exception as exc:
            logger.exception("General chat failed")
            return GeneralChatResponse(
                capability="general",
                intent="chat",
                answer="I'm sorry, I encountered an error processing your request. Please try again.",
                status="error",
            )
