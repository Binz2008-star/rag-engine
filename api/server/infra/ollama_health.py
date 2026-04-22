from __future__ import annotations
import logging
from typing import Final

import httpx

log = logging.getLogger(__name__)

_TIMEOUT: Final = httpx.Timeout(2.0, connect=1.0)


class OllamaUnavailableError(RuntimeError):
    pass


async def check_ollama(base_url: str, required_models: list[str]) -> None:
    url = f"{base_url.rstrip('/')}/api/tags"
    try:
        async with httpx.AsyncClient(timeout=_TIMEOUT) as c:
            r = await c.get(url)
            r.raise_for_status()
            # Strip tag suffix (e.g., ":latest") for flexible matching
            installed = {m["name"].split(":")[0] for m in r.json().get("models", [])}
    except (httpx.HTTPError, ValueError) as e:
        raise OllamaUnavailableError(f"Ollama unreachable at {base_url}: {e}") from e

    missing = [m for m in required_models if m not in installed]
    if missing:
        raise OllamaUnavailableError(f"Missing Ollama models: {missing}")
