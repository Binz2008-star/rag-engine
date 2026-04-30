from __future__ import annotations

import json
import time

from app.config import ACTIVE_MODEL_PATH, GENERATION_TOP_K, REFUSAL_MESSAGE
from app.models import KnowledgeGap, PipelineResult
from app.query_normalizer import is_arabic
from app.utils import stable_hash
from router.features import normalize_query
from generation.grounding import check_grounding
from app.reranker import LightweightReranker
from analysis.corpus_topic_map import CorpusTopicMap


_SENSITIVE_PATTERNS = [
    "uranium", "enrichment", "nuclear plant", "nuclear power station",
    "radioactive", "biological weapon", "chemical weapon",
]


def _is_sensitive_query(query: str) -> bool:
    q = query.lower()
    return any(p in q for p in _SENSITIVE_PATTERNS)


def _has_sufficient_overlap(query: str, chunks: list) -> bool:
    """Check if query has sufficient term overlap with retrieved chunks."""
    q_terms = set(query.lower().split())
    if not q_terms:
        return False
    ctx_text = " ".join(c.text.lower() for c in chunks)
    hits = sum(1 for t in q_terms if t in ctx_text)
    return hits >= 1


class Pipeline:
    def __init__(
        self,
        router,
        embedder,
        retriever,
        llm,
        reranker: LightweightReranker | None = None,
        knowledge_gap_analyzer=None,
    ):
        self.router = router
        self.embedder = embedder
        self.retriever = retriever
        self.llm = llm
        self.reranker = reranker
        # Lazy-import the analyzer only when the caller does not inject one.
        # analysis.knowledge_gap imports `requests`, which is intentionally
        # absent from the lightweight CI lane; keeping this import off the
        # module path lets `import app.pipeline` succeed without requests.
        if knowledge_gap_analyzer is None:
            from analysis.knowledge_gap import KnowledgeGapAnalyzer
            knowledge_gap_analyzer = KnowledgeGapAnalyzer(llm)
        self.knowledge_gap_analyzer = knowledge_gap_analyzer
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
            hits = self.reranker.rerank(hits, normalized_query, top_k=GENERATION_TOP_K)
        else:
            hits = hits[:GENERATION_TOP_K]

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

        # Translate Arabic queries to English before overlap check and generation.
        # normalized_query is preserved for logging; generation_query is English-only.
        if is_arabic(normalized_query):
            generation_query = self.llm.translate_to_english(normalized_query)
            if not generation_query or generation_query == normalized_query:
                # Translation failed — degrade to refusal rather than
                # passing Arabic into the English overlap gate
                elapsed_ms = int((time.perf_counter() - t0) * 1000)
                return PipelineResult(
                    query_id=query_id,
                    query=query,
                    normalized_query=normalized_query,
                    intent=route.intent,
                    confidence=route.confidence,
                    intent_method=route.intent_method,
                    retrieval=hits,
                    answer=REFUSAL_MESSAGE,
                    grounded=True,
                    failure_type="translation_failure",
                    knowledge_gap=None,
                    latency_ms=elapsed_ms,
                    model_version=self.model_version,
                    retriever_version=self.retriever_version,
                )
        else:
            generation_query = normalized_query

        # Hard grounding gate: use English query for term overlap
        if not _has_sufficient_overlap(generation_query, hits):
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
                knowledge_gap=None,
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

        answer = self.llm.generate(generation_query, hits)
        normalized_answer = answer.strip().lower()

        speculative_prefixes = (
            "based on the context",
            "it appears",
            "it can be inferred",
            "this suggests",
            "likely",
            "used cooking oil",
            "uco",
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
            # Authoritative grounding: same logic as evaluator (sentence-level
            # semantic cosine at 0.60). If the evaluator would reject this
            # answer as ungrounded, the product must also reject it.
            # Unifying the two removes split-brain between runtime and eval.
            grounded = check_grounding(answer, hits, self.embedder.embed_batch)
            if not grounded:
                answer = "Insufficient data."
                grounded = True
                failure_type = "retrieval_miss"
                knowledge_gap = self._analyze_gap(query, route.intent, normalized_query)
            else:
                failure_type = None
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
