from __future__ import annotations

import json
import time

from app.config import ACTIVE_MODEL_PATH
from app.models import PipelineResult
from app.utils import stable_hash
from events.emitter import emit
from generation.grounding import check_grounding
from router.features import normalize_query


class Pipeline:
    def __init__(self, router, embedder, retriever, llm):
        self.router = router
        self.embedder = embedder
        self.retriever = retriever
        self.llm = llm

        if ACTIVE_MODEL_PATH.exists():
            meta = json.loads(ACTIVE_MODEL_PATH.read_text(encoding="utf-8"))
            self.model_version = meta.get("version", "unknown")
        else:
            self.model_version = "unknown"

        sample_ids: list[str] = []
        for index in retriever.indexes.values():
            sample_ids.extend(chunk.chunk_id for chunk in index.chunks[:100])
        self.retriever_version = (
            f"{getattr(retriever, 'version', 'unknown')}_{stable_hash(sample_ids)[:8]}"
        )

    def run(self, query: str, query_id: str) -> PipelineResult:
        t0 = time.perf_counter()
        normalized_query = normalize_query(query)
        terminal_emitted = False

        try:
            route = self.router.route(normalized_query)
            vec = self.embedder.embed_batch([normalized_query])[0]
            hits = self.retriever.retrieve(
                vec,
                route.intent,
                query=normalized_query,
                query_id=query_id,
            )
            answer = self.llm.generate(normalized_query, hits)
            grounded = check_grounding(answer, hits, self.embedder.embed_batch)

            if not hits:
                failure_type = "retrieval_miss"
            elif not grounded:
                failure_type = "hallucination"
            else:
                failure_type = None

            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            result = PipelineResult(
                query_id=query_id,
                query=query,
                normalized_query=normalized_query,
                intent=route.intent,
                confidence=route.confidence,
                intent_method=route.intent_method,
                retrieval=hits,
                answer=answer,
                grounded=grounded,
                failure_type=failure_type,
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

            emit(
                "query_completed",
                {
                    "query_id": result.query_id,
                    "query": result.query,
                    "normalized_query": result.normalized_query,
                    "intent": result.intent,
                    "confidence": result.confidence,
                    "intent_method": result.intent_method,
                    "answer": result.answer,
                    "grounded": result.grounded,
                    "failure_type": result.failure_type,
                    "latency_ms": result.latency_ms,
                    "retrieval_count": len(result.retrieval),
                },
            )
            terminal_emitted = True
            return result
        except Exception as exc:
            emit(
                "query_failed",
                {
                    "query_id": query_id,
                    "query": query,
                    "normalized_query": normalized_query,
                    "error": str(exc),
                },
            )
            terminal_emitted = True
            raise
        finally:
            if not terminal_emitted:
                emit(
                    "query_failed",
                    {
                        "query_id": query_id,
                        "query": query,
                        "normalized_query": normalized_query,
                        "error": "pipeline exited without terminal event",
                    },
                )
