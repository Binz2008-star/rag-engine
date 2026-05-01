"""Embedding generation - converts text to vectors using Ollama."""

from __future__ import annotations

import logging
import time
from typing import List

import numpy as np
import requests

from app.config import BATCH_SIZE, EMBED_MODEL, MAX_RETRIES, OLLAMA_BASE_URL, TIMEOUT

logger = logging.getLogger(__name__)


class EmbeddingClient:
    """Generate embeddings from text using Ollama."""

    def __init__(self) -> None:
        self.base_url = OLLAMA_BASE_URL.rstrip("/")
        self.timeout = TIMEOUT
        self.session = requests.Session()

    def close(self) -> None:
        self.session.close()

    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed a batch of texts with retry logic."""
        if not texts:
            raise ValueError("embed_batch called with empty input.")

        for i, text in enumerate(texts):
            if not isinstance(text, str):
                raise TypeError(f"Text at index {i} is not a string.")
            if not text.strip():
                logger.warning("Text at index %d is empty/whitespace only.", i)

        total_chars = sum(len(t) for t in texts)
        last_error: Exception | None = None

        for attempt in range(1, MAX_RETRIES + 1):
            t0 = time.perf_counter()
            logger.info(
                "Embed request attempt %d/%d: model=%s, texts=%d, chars=%d",
                attempt,
                MAX_RETRIES,
                EMBED_MODEL,
                len(texts),
                total_chars,
            )

            try:
                response = self.session.post(
                    f"{self.base_url}/api/embed",
                    json={"model": EMBED_MODEL, "input": texts},
                    timeout=self.timeout,
                )
                response.raise_for_status()
                data = response.json()

                if "embeddings" not in data:
                    raise ValueError(f"Missing 'embeddings' in response: {data}")

                arr = np.asarray(data["embeddings"], dtype=np.float32)

                if arr.ndim != 2:
                    raise ValueError(f"Expected 2D embedding array, got shape={arr.shape}")

                if arr.shape[0] != len(texts):
                    raise ValueError(
                        f"Embedding row count mismatch: expected {len(texts)}, got {arr.shape[0]}"
                    )

                if arr.shape[1] <= 0:
                    raise ValueError(f"Invalid embedding dimension: {arr.shape[1]}")

                if not np.isfinite(arr).all():
                    raise ValueError("Embeddings contain NaN or Inf values.")

                arr = self._normalize_rows(arr)

                elapsed = time.perf_counter() - t0
                logger.info(
                    "Embed request succeeded: status=%d, shape=%s, elapsed=%.3fs",
                    response.status_code,
                    arr.shape,
                    elapsed,
                )
                return arr

            except Exception as exc:
                last_error = exc
                elapsed = time.perf_counter() - t0
                logger.error(
                    "Embed attempt %d/%d failed after %.3fs: type=%s, message=%s, model=%s, texts=%d, chars=%d",
                    attempt,
                    MAX_RETRIES,
                    elapsed,
                    type(exc).__name__,
                    str(exc),
                    EMBED_MODEL,
                    len(texts),
                    total_chars,
                )
                if attempt < MAX_RETRIES:
                    time.sleep(2 ** (attempt - 1))
                else:
                    logger.error("Embedding failed permanently - deterministic infra failure")
                    raise RuntimeError("Embedding failure - deterministic infra failure") from last_error

        raise RuntimeError(f"Embedding failed after {MAX_RETRIES} attempts") from last_error

    def embed_chunks(self, chunks: List) -> np.ndarray:
        """Embed all chunks in batches."""
        if not chunks:
            raise ValueError("embed_chunks called with no chunks.")

        all_embeddings: List[np.ndarray] = []
        total = len(chunks)
        n_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE

        logger.info("Starting chunk embedding: total_chunks=%d, batch_size=%d, n_batches=%d", total, BATCH_SIZE, n_batches)

        for start in range(0, total, BATCH_SIZE):
            batch = chunks[start : start + BATCH_SIZE]
            batch_num = start // BATCH_SIZE + 1

            # Log sources in this batch for tracing
            sources_in_batch = sorted(set(c.source for c in batch))
            logger.info(
                "Embedding batch %d/%d: chunks=%d, sources=%s",
                batch_num,
                n_batches,
                len(batch),
                sources_in_batch,
            )

            embeddings = self.embed_batch([c.text for c in batch])
            all_embeddings.append(embeddings)

        result = np.vstack(all_embeddings)

        if result.shape[0] != total:
            raise ValueError(f"Final embedding count mismatch: expected {total}, got {result.shape[0]}")

        logger.info("Chunk embedding completed: shape=%s", result.shape)
        return result

    @staticmethod
    def _normalize_rows(arr: np.ndarray) -> np.ndarray:
        """L2-normalize rows safely."""
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms == 0.0, 1.0, norms)
        return arr / norms
