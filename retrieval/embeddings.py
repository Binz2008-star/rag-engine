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

    def warmup(self) -> None:
        try:
            self.embed("warmup")
            logger.info("Embedding warmup succeeded for model=%s", self.model)
        except Exception:
            logger.warning(
                "Embedding warmup failed for model=%s", self.model, exc_info=True
            )

    def embed_batch(self, texts: list[str]) -> np.ndarray:
        if not texts:
            raise ValueError("embed_batch called with empty input")

        last_exc: Exception | None = None

        for attempt in range(MAX_RETRIES):
            try:
                started = time.perf_counter()
                response = self.session.post(
                    f"{self.base_url}/api/embed",
                    json={
                        "model": self.model,
                        "input": texts,
                        "keep_alive": "10m",
                    },
                    timeout=(5, max(self.timeout, 30)),
                )
                response.raise_for_status()

                payload = response.json()
                embeddings = payload.get("embeddings")
                if not embeddings:
                    raise RuntimeError("Embedding response missing 'embeddings'")

                arr = np.array(embeddings, dtype=np.float32)
                norms = np.linalg.norm(arr, axis=1, keepdims=True)
                norms = np.where(norms == 0, 1.0, norms)

                elapsed_ms = int((time.perf_counter() - started) * 1000)
                logger.info(
                    "Embedding batch succeeded model=%s count=%d latency_ms=%d",
                    self.model,
                    len(texts),
                    elapsed_ms,
                )

                return arr / norms

            except requests.HTTPError as exc:
                last_exc = exc
                status_code = exc.response.status_code if exc.response is not None else -1

                logger.warning(
                    "Embedding HTTP error model=%s attempt=%d/%d status=%s",
                    self.model,
                    attempt + 1,
                    MAX_RETRIES,
                    status_code,
                    exc_info=True,
                )

                if status_code < 500 and status_code != 429:
                    break

            except requests.RequestException as exc:
                last_exc = exc
                logger.warning(
                    "Embedding request error model=%s attempt=%d/%d",
                    self.model,
                    attempt + 1,
                    MAX_RETRIES,
                    exc_info=True,
                )

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Embedding unexpected error model=%s attempt=%d/%d",
                    self.model,
                    attempt + 1,
                    MAX_RETRIES,
                    exc_info=True,
                )

            if attempt < MAX_RETRIES - 1:
                time.sleep(min(2**attempt, 8))

        raise RuntimeError(
            f"Embedding failed after retries for model={self.model}: {last_exc}"
        )

    def embed(self, text: str) -> np.ndarray:
        return self.embed_batch([text])[0]
