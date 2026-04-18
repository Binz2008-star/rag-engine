from __future__ import annotations

import json
import time

from app.config import ACTIVE_MODEL_PATH
from app.models import PipelineResult
from app.utils import stable_hash
from router.features import normalize_query
from generation.grounding import check_grounding
from retrieval.reranker import Reranker


class Pipeline:
    def __init__(self, router, embedder, retriever, llm, reranker: Reranker | None = None):
        self.router = router
        self.embedder = embedder
        self.retriever = retriever
        self.llm = llm
        self.reranker = reranker

        if ACTIVE_MODEL_PATH.exists():
            meta = json.loads(ACTIVE_MODEL_PATH.read_text(encoding="utf-8"))
            self.model_version = meta.get("version", "unknown")
        else:
            self.model_version = "unknown"

        sample_ids: list[str] = []
        for idx in retriever.indexes.values():
            sample_ids.extend(c.chunk_id for c in idx.chunks[:100])
        self.retriever_version = f"{getattr(retriever, 'version', 'unknown')}_{stable_hash(sample_ids)[:8]}"

    def run(self, query: str, query_id: str) -> PipelineResult:
        t0 = time.perf_counter()
        normalized_query = normalize_query(query)
        route = self.router.route(normalized_query)
        vec = self.embedder.embed_batch([normalized_query])[0]

        hits = self.retriever.retrieve(vec, route.intent, normalized_query)

        if not hits:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return PipelineResult(
                query_id=query_id,
                query=query,
                normalized_query=normalized_query,
                intent=route.intent,
                confidence=route.confidence,
                intent_method=route.intent_method,
                retrieval=[],
                answer="Insufficient data.",
                grounded=True,
                failure_type="retrieval_miss",
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

        if self.reranker:
            hits = self.reranker.rerank(hits, normalized_query, top_k=len(hits))

        if hits and hits[0].score < 0.20:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return PipelineResult(
                query_id=query_id,
                query=query,
                normalized_query=normalized_query,
                intent=route.intent,
                confidence=route.confidence,
                intent_method=route.intent_method,
                retrieval=hits,
                answer="Insufficient data.",
                grounded=True,
                failure_type="retrieval_miss",
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

        answer = self.llm.generate(normalized_query, hits)
        normalized_answer = answer.strip().lower()

        speculative_prefixes = (
            "based on the context",
            "it appears",
            "it can be inferred",
            "this suggests",
            "likely",
        )

        if normalized_answer.startswith(speculative_prefixes):
            answer = "Insufficient data."
            grounded = True
            failure_type = "retrieval_miss"
        elif normalized_answer.startswith("insufficient data"):
            answer = "Insufficient data."
            grounded = True
            failure_type = "retrieval_miss"
        else:
            grounded = check_grounding(answer, hits, self.embedder.embed_batch)
            failure_type = None if grounded else "hallucination"

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        return PipelineResult(
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

    def close(self) -> None:
        """No-op close method for CI compatibility."""
        return None
