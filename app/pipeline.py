from __future__ import annotations

import json
import time

from app.config import ACTIVE_MODEL_PATH, REFUSAL_MESSAGE
from app.models import KnowledgeGap, PipelineResult
from app.utils import stable_hash
from router.features import normalize_query
from generation.grounding import check_grounding
from retrieval.reranker import Reranker
from analysis.corpus_topic_map import CorpusTopicMap
from analysis.knowledge_gap import KnowledgeGapAnalyzer


_SENSITIVE_PATTERNS = [
    "uranium", "enrichment", "nuclear plant", "nuclear power station",
    "radioactive", "biological weapon", "chemical weapon",
]


def _is_sensitive_query(query: str) -> bool:
    q = query.lower()
    return any(p in q for p in _SENSITIVE_PATTERNS)


class Pipeline:
    def __init__(self, router, embedder, retriever, llm, reranker: Reranker | None = None):
        self.router = router
        self.embedder = embedder
        self.retriever = retriever
        self.llm = llm
        self.reranker = reranker
        self.knowledge_gap_analyzer = KnowledgeGapAnalyzer(llm)
        self.corpus_topic_map = CorpusTopicMap(retriever.indexes)

        if ACTIVE_MODEL_PATH.exists():
            meta = json.loads(ACTIVE_MODEL_PATH.read_text(encoding="utf-8"))
            self.model_version = meta.get("version", "unknown")
        else:
            self.model_version = "unknown"

        sample_ids: list[str] = []
        for idx in retriever.indexes.values():
            sample_ids.extend(c.chunk_id for c in idx.chunks[:100])
        self.retriever_version = f"{getattr(retriever, 'version', 'unknown')}_{stable_hash(sample_ids)[:8]}"

    def _analyze_gap(self, query: str, intent: str, normalized_query: str) -> KnowledgeGap:
        """Run LLM gap analysis and enrich with deterministic corpus coverage."""
        gap = self.knowledge_gap_analyzer.analyze(query, intent, normalized_query)
        missing = self.corpus_topic_map.missing_documents_for(query, intent)
        gap.missing_documents = missing
        gap.missing_confidence = 1.0 if missing else 0.0
        return gap

    def run(self, query: str, query_id: str) -> PipelineResult:
        t0 = time.perf_counter()
        normalized_query = normalize_query(query)

        # Refuse empty or very short queries
        if len(normalized_query.strip()) < 3:
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return PipelineResult(
                query_id=query_id,
                query=query,
                normalized_query=normalized_query,
                intent="general",
                confidence=1.0,
                intent_method="rule",
                retrieval=[],
                answer=REFUSAL_MESSAGE,
                grounded=True,
                failure_type="retrieval_miss",
                knowledge_gap=None,
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

        route = self.router.route(normalized_query)
        vec = self.embedder.embed_batch([normalized_query])[0]

        # Refuse sensitive queries after routing (for domain accuracy)
        if _is_sensitive_query(query):
            elapsed_ms = int((time.perf_counter() - t0) * 1000)
            return PipelineResult(
                query_id=query_id,
                query=query,
                normalized_query=normalized_query,
                intent=route.intent,
                confidence=route.confidence,
                intent_method=route.intent_method,
                retrieval=[],
                answer=REFUSAL_MESSAGE,
                grounded=True,
                failure_type="retrieval_miss",
                knowledge_gap=None,
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

        hits = self.retriever.retrieve(vec, route.intent, normalized_query)

        if not hits:
            knowledge_gap = self._analyze_gap(query, route.intent, normalized_query)
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
                knowledge_gap=knowledge_gap,
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

        if self.reranker:
            hits = self.reranker.rerank(hits, normalized_query, top_k=len(hits))

        if hits and hits[0].score < 0.20:
            knowledge_gap = self._analyze_gap(query, route.intent, normalized_query)
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
                knowledge_gap=knowledge_gap,
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
            knowledge_gap = self._analyze_gap(query, route.intent, normalized_query)
        elif normalized_answer.startswith("insufficient data"):
            answer = "Insufficient data."
            grounded = True
            failure_type = "retrieval_miss"
            knowledge_gap = self._analyze_gap(query, route.intent, normalized_query)
        else:
            grounded = check_grounding(answer, hits, self.embedder.embed_batch)
            failure_type = None if grounded else "hallucination"
            knowledge_gap = None

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
            knowledge_gap=knowledge_gap,
            latency_ms=elapsed_ms,
            model_version=self.model_version,
            retriever_version=self.retriever_version,
        )

    def close(self) -> None:
        """No-op close method for CI compatibility."""
        return None
