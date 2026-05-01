from __future__ import annotations

import logging
import time

import numpy as np
import requests

from app.config import EMBED_MODEL, MAX_RETRIES, OLLAMA_BASE_URL, TIMEOUT

logger = logging.getLogger(__name__)


class Embedder:
    def __init__(
        self,
        base_url: str = OLLAMA_BASE_URL,
        model: str = EMBED_MODEL,
        timeout: int = TIMEOUT,
    ):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout = timeout
        self.session = requests.Session()

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            raise ValueError("embed_batch called with empty input")

        last_exc: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self.session.post(
                    f"{self.base_url}/api/embed",
                    json={"model": self.model, "input": texts},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                arr = np.array(response.json()["embeddings"], dtype=np.float32)
                norms = np.linalg.norm(arr, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1.0, norms)
                return arr / norms
            except (
                requests.exceptions.Timeout,
                requests.exceptions.ConnectionError,
                requests.exceptions.HTTPError,
                ValueError,
                KeyError,
            ) as exc:
                last_exc = exc
                logger.warning(
                    "Embedding attempt %d/%d failed: %s: %s",
                    attempt + 1,
                    MAX_RETRIES,
                    type(exc).__name__,
                    str(exc)[:100],
                )
                time.sleep(2**attempt)

        raise RuntimeError(f"Embedding failed after {MAX_RETRIES} retries: {type(last_exc).__name__}: {last_exc}")

    def embed(self, text: str) -> np.ndarray:
        return self.embed_batch([text])[0]
