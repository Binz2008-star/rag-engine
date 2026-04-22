"""Async adapter around the eval-certified pipeline.

The HTTP surface must serve the exact same pipeline that CI certifies via
`eval_runner.py`. Any divergence means the strict gate proves nothing about
the product. This module therefore wires up `app.pipeline.Pipeline` and
`app.inference_service.InferenceService` using the identical construction
pattern as `eval_runner.main()`.

Streaming is deliberately not implemented: `Pipeline.run()` is a blocking
call that returns a fully-formed `PipelineResult`. A faked SSE layer on top
would be UI theatre, not a product guarantee. Streaming is in scope only
when the evaluated pipeline gains native token streaming.
"""

from __future__ import annotations

import asyncio
import logging
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.inference_service import InferenceService
from app.models import PipelineResult
from app.pipeline import Pipeline
from generation.llm import LLMClient
from retrieval.embeddings import Embedder
from retrieval.faiss_index import FaissIndex
from retrieval.multi_retriever import MultiRetriever
from retrieval.reranker import Reranker
from router.intent_router import IntentRouter


logger = logging.getLogger(__name__)

# Directory layout contract inherited from `eval_runner.py`: FAISS indexes
# are built under `models/` by `scripts/build_indexes.py`.
_INDEX_DIR_DEFAULT = Path("models")
_INTENTS: tuple[str, ...] = ("cv", "eco", "general")


class PipelineNotReadyError(RuntimeError):
    """Raised when a request arrives before pipeline initialisation finished."""


class RagService:
    """Async facade over the synchronous evaluated pipeline.

    All blocking pipeline calls run on a worker thread so FastAPI's event
    loop stays responsive under concurrent requests. The pipeline itself is
    constructed once at startup and re-used for every request.
    """

    def __init__(self, *, index_dir: Path | None = None) -> None:
        self._index_dir = index_dir or _INDEX_DIR_DEFAULT
        self._pipeline: Optional[Pipeline] = None
        self._service: Optional[InferenceService] = None
        self._llm: Optional[LLMClient] = None
        self._ready = False
        self._index_count = 0
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    async def startup(self) -> None:
        """Build the pipeline exactly like `eval_runner.py` does."""
        async with self._lock:
            if self._service is not None:
                return
            self._service = await asyncio.to_thread(self._build_service)
            if hasattr(self._pipeline, "embedder") and self._pipeline.embedder is not None:
                try:
                    self._pipeline.embedder.warmup()
                except Exception:
                    logger.warning("Embedder warmup failed", exc_info=True)
            self._ready = True
            logger.info(
                "RAG pipeline ready (indexes=%d)", self._index_count
            )

    async def shutdown(self) -> None:
        """Release resources."""
        self._pipeline = None
        self._service = None
        self._llm = None
        self._ready = False

    @property
    def ready(self) -> bool:
        return self._ready and self._service is not None

    @property
    def index_count(self) -> int:
        return self._index_count

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def query(self, question: str) -> Dict[str, Any]:
        """Run a question through the evaluated pipeline.

        Returns a plain dict shaped for the HTTP response. Mirrors
        `eval_runner.query_fn` so the API view matches what CI validates.
        """
        service = self._require_service()
        query_id = f"api_{int(time.time() * 1000)}"
        t0 = time.perf_counter()
        result: PipelineResult = await asyncio.to_thread(
            service.handle_query, question, query_id
        )
        wall_ms = int((time.perf_counter() - t0) * 1000)
        return _result_to_payload(result, wall_ms)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _require_service(self) -> InferenceService:
        if self._service is None or not self._ready:
            raise PipelineNotReadyError("Pipeline is not initialised")
        return self._service

    def _build_service(self) -> InferenceService:
        """Mirrors the initialisation block in `eval_runner.main()`.

        Keeping the two paths identical is the only guarantee that a PASS
        from the strict eval means the API will behave the same way.
        """
        logger.info("Initialising IntentRouter from active model")
        router = IntentRouter.from_active_model()

        logger.info("Initialising Embedder")
        embedder = Embedder()

        logger.info("Loading FAISS indexes from %s", self._index_dir)
        indexes: dict[str, FaissIndex] = {}
        for name in _INTENTS:
            try:
                indexes[name] = FaissIndex.load(name, out_dir=self._index_dir)
            except FileNotFoundError:
                logger.warning("FAISS index missing for intent %s", name)
                continue

        if not indexes:
            raise RuntimeError(
                f"No FAISS indexes found under {self._index_dir}; "
                "run scripts/build_indexes.py first"
            )

        self._index_count = len(indexes)
        retriever = MultiRetriever(indexes=indexes)
        reranker = Reranker(embed_fn=embedder.embed_batch)
        llm = LLMClient()
        self._llm = llm

        pipeline = Pipeline(
            router=router,
            embedder=embedder,
            retriever=retriever,
            llm=llm,
            reranker=reranker,
        )
        self._pipeline = pipeline
        return InferenceService(pipeline=pipeline)


# ─── Response shaping ──────────────────────────────────────────────────────
# The API payload is the minimal honest projection of `PipelineResult`. We
# expose `latency_ms` because that is what the pipeline actually measures;
# inventing split retrieval/generation timings would fabricate data the
# canonical pipeline does not record.


def _result_to_payload(result: PipelineResult, wall_ms: int) -> Dict[str, Any]:
    sources: List[Dict[str, str]] = []
    for hit in result.retrieval:
        sources.append(
            {
                "source": str(getattr(hit, "source", "") or ""),
                "chunk_id": str(getattr(hit, "chunk_id", "") or ""),
                "doc_type": str(getattr(hit, "doc_type", "") or ""),
                "score": float(getattr(hit, "score", 0.0) or 0.0),
            }
        )

    # `intent_method` reported to clients follows the same derivation as
    # `eval_runner.query_fn` so dashboards and API consumers agree on the
    # label. The router reports the raw method; the runner collapses it
    # to a coarse class for metrics.
    intent_method_raw = result.intent_method or ""
    intent_method_coarse = (
        "rules" if (result.confidence or 0.0) >= 0.85 else "v2_model"
    )

    return {
        "answer": result.answer or "",
        "sources": sources,
        "latency_ms": int(result.latency_ms or 0),
        "wall_ms": wall_ms,
        "request_id": result.query_id,
        "intent": result.intent or "",
        "intent_confidence": float(result.confidence or 0.0),
        "intent_method": intent_method_coarse,
        "intent_method_raw": intent_method_raw,
        "grounded": bool(result.grounded),
        "failure_type": result.failure_type,
        "model_version": result.model_version or "",
        "retriever_version": result.retriever_version or "",
    }
