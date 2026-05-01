from __future__ import annotations

import json
import logging
import os
import time

import numpy as np

from app.config import ACTIVE_MODEL_PATH, REFUSAL_MESSAGE
from app.models import FailureType, KnowledgeGap, PipelineResult
from app.query_normalizer import is_arabic
from app.utils import stable_hash
from router.features import normalize_query
from generation.grounding import check_grounding
from generation.reasoning import ReasoningVerifier
from generation.self_correcting import SelfCorrectingGenerator
from retrieval.reranker import Reranker
from analysis.corpus_topic_map import CorpusTopicMap


logger = logging.getLogger(__name__)

_SENSITIVE_PATTERNS = [
    "uranium", "enrichment", "nuclear plant", "nuclear power station",
    "radioactive", "biological weapon", "chemical weapon",
]


def _is_sensitive_query(query: str) -> bool:
    q = query.lower()
    return any(p in q for p in _SENSITIVE_PATTERNS)


def _has_sufficient_overlap(query: str, chunks: list, embedder) -> bool:
    """Check if query has sufficient semantic similarity with retrieved chunks."""
    if not chunks:
        return False

    # Use semantic similarity instead of primitive term overlap
    query_embedding = embedder.embed_batch([query])[0]
    chunk_texts = [c.text for c in chunks]
    chunk_embeddings = embedder.embed_batch(chunk_texts)

    # Calculate max similarity between query and any chunk
    max_similarity = 0.0
    for chunk_emb in chunk_embeddings:
        # Cosine similarity
        similarity = float(
            (query_embedding @ chunk_emb) /
            (np.linalg.norm(query_embedding) * np.linalg.norm(chunk_emb) + 1e-8)
        )
        max_similarity = max(max_similarity, similarity)

    # Threshold: need at least 0.30 similarity to proceed
    return max_similarity >= 0.30


class Pipeline:
    def __init__(
        self,
        router,
        embedder,
        retriever,
        llm,
        reranker: Reranker | None = None,
        knowledge_gap_analyzer=None,
        reasoning_verifier: ReasoningVerifier | None = None,
        self_correcting: SelfCorrectingGenerator | None = None,
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
        self.reasoning_verifier = reasoning_verifier or ReasoningVerifier()

        # Check for evaluation fast mode: disable self-correction
        _enable_self_correction = os.environ.get("EVAL_SELF_CORRECTION", "1") not in ("0", "false", "False")
        if _enable_self_correction:
            self.self_correcting = self_correcting or SelfCorrectingGenerator(max_retries=2)
        else:
            self.self_correcting = None  # Disabled for fast eval

        if ACTIVE_MODEL_PATH.exists():
            meta = json.loads(ACTIVE_MODEL_PATH.read_text(encoding="utf-8"))
            self.model_version = meta.get("version", "unknown")
        else:
            self.model_version = "unknown"

        sample_ids: list[str] = []
        for idx in retriever.indexes.values():
            sample_ids.extend(c.chunk_id for c in idx.chunks[:100])
        self.retriever_version = f"{getattr(retriever, 'version', 'unknown')}_{stable_hash(sample_ids)[:8]}"

    def _build_cited_context(self, hits: list, max_chars: int = 4200) -> str:
        """
        Build cited context with RAGFlow-style [S1], [S2] formatting.

        Each chunk includes source metadata and score for transparency.
        """
        parts = []
        total = 0

        for idx, hit in enumerate(hits, start=1):
            # Build citation header with metadata
            location = f", page={hit.page}" if hasattr(hit, 'page') and hit.page else ""
            section = f", section={hit.section}" if hasattr(hit, 'section') and hit.section else ""
            header = f"[S{idx}: source={hit.source}, chunk={hit.chunk_id}{location}{section}, score={hit.score:.3f}]"

            part = f"{header}\n{hit.text.strip()}"

            if total + len(part) > max_chars:
                break

            parts.append(part)
            total += len(part)

        return "\n\n".join(parts)

    def _shape_context(self, hits: list, intent: str) -> list:
        """
        Shape and optimize context before generation.

        Strategies:
        1. Diversify sources (avoid clustering on same document)
        2. Boost CV-specific chunks for cv intent
        3. Reorder by relevance score
        4. Truncate to max context size
        """
        if not hits:
            return hits

        # Group by source to diversify
        source_seen = set()
        diversified = []
        others = []

        for hit in hits:
            if hit.source not in source_seen:
                diversified.append(hit)
                source_seen.add(hit.source)
            else:
                others.append(hit)

        # Append remaining hits
        shaped = diversified + others

        # Intent-specific boosting
        if intent == "cv":
            # Boost CV-specific sources
            shaped.sort(key=lambda h: (
                0 if "cv" in h.doc_type.lower() or "roben" in h.source.lower() else 1,
                -h.score
            ))
        else:
            # Sort by score
            shaped.sort(key=lambda h: -h.score)

        # Limit to top-k for context window
        max_context_hits = 5
        return shaped[:max_context_hits]

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
                failure_type=FailureType.ROUTING_MISS,
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
                failure_type=FailureType.SENSITIVE_REJECT,
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
                failure_type=FailureType.RETRIEVAL_EMPTY,
                knowledge_gap=knowledge_gap,
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

        # Check for evaluation fast mode: optionally skip reranking
        _enable_rerank = os.environ.get("EVAL_RERANK", "1") not in ("0", "false", "False")
        if self.reranker and _enable_rerank:
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
                failure_type=FailureType.RETRIEVAL_LOW_SCORE,
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
                    failure_type=FailureType.TRANSLATION_FAILURE,
                    knowledge_gap=None,
                    latency_ms=elapsed_ms,
                    model_version=self.model_version,
                    retriever_version=self.retriever_version,
                )
        else:
            generation_query = normalized_query

        # Hard grounding gate: use semantic similarity instead of term overlap
        if not _has_sufficient_overlap(generation_query, hits, self.embedder):
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
                failure_type=FailureType.TERM_OVERLAP_MISS,
                knowledge_gap=None,
                latency_ms=elapsed_ms,
                model_version=self.model_version,
                retriever_version=self.retriever_version,
            )

        # Context shaping: optimize retrieval hits before generation
        shaped_hits = self._shape_context(hits, route.intent)

        # Self-correcting generation with retry strategies
        def generate_with_prompt(query: str, prompt: str) -> str:
            """Generate answer using LLM with custom prompt."""
            # Build cited context from shaped hits
            context = self._build_cited_context(shaped_hits)
            full_prompt = f"""Answer the following question using ONLY the provided context.
Use citations like [S1], [S2] to reference sources.

Context:
{context}

Question: {query}

{prompt}
"""
            return self.llm._generate_with_prompt(full_prompt)

        def check_grounding_wrapper(answer: str, hits_list: list) -> bool:
            """Wrapper for grounding check."""
            return check_grounding(answer, hits_list, self.embedder.embed_batch)

        def check_reasoning_wrapper(answer: str, hits_list: list) -> tuple[bool, object]:
            """Wrapper for reasoning check."""
            return self.reasoning_verifier.verify(answer, hits_list, self.embedder.embed_batch)

        # Initial generation
        initial_answer = self.llm.generate(generation_query, shaped_hits)
        normalized_answer = initial_answer.strip().lower()

        # Initial validation - DO NOT replace with refusal yet
        initial_grounded = True
        initial_reasoning_valid = True
        initial_failure_type = None

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
            initial_grounded = True
            initial_reasoning_valid = True
            initial_failure_type = FailureType.SPECULATIVE_REJECT
        elif normalized_answer.startswith("insufficient data"):
            initial_grounded = True
            initial_reasoning_valid = True
            initial_failure_type = FailureType.GROUNDING_REJECT
        else:
            # Authoritative grounding check
            initial_grounded = check_grounding(initial_answer, hits, self.embedder.embed_batch)
            if not initial_grounded:
                initial_failure_type = FailureType.GROUNDING_REJECT
            else:
                # Reasoning verifier check
                initial_reasoning_valid, reasoning_breakdown = self.reasoning_verifier.verify(
                    initial_answer, hits, self.embedder.embed_batch
                )
                if not initial_reasoning_valid:
                    initial_failure_type = FailureType.REASONING_REJECT
                    if logger.isEnabledFor(logging.DEBUG):
                        logger.debug(
                            "Reasoning check failed: premise=%s flow=%s no_spec=%s conclusion=%s score=%.2f",
                            reasoning_breakdown.has_premise_support,
                            reasoning_breakdown.has_logical_flow,
                            reasoning_breakdown.avoids_speculation,
                            reasoning_breakdown.has_conclusion_link,
                            reasoning_breakdown.final_score,
                        )

        # Grounding gate is AUTHORITATIVE (fail-closed per v1.0 contract)
        # If grounding fails, refuse immediately - no self-correction allowed
        if not initial_grounded:
            answer = "Insufficient data."
            grounded = True
            failure_type = FailureType.GROUNDING_REJECT
            knowledge_gap = self._analyze_gap(query, route.intent, normalized_query)
            retry_attempts = 0
            corrected = False
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
                retry_attempts=retry_attempts,
                corrected=corrected,
            )

        # Apply self-correction only for reasoning failures (not grounding)
        correction_result = None
        if not initial_reasoning_valid and self.self_correcting is not None:
            correction_result = self.self_correcting.correct(
                query=generation_query,
                initial_answer=initial_answer,
                hits=hits,
                initial_failure_type=initial_failure_type,
                initial_grounded=initial_grounded,
                initial_reasoning_valid=initial_reasoning_valid,
                generate_fn=generate_with_prompt,
                check_grounding_fn=check_grounding_wrapper,
                check_reasoning_fn=check_reasoning_wrapper,
            )

            answer = correction_result.final_answer
            grounded = correction_result.final_grounded
            reasoning_valid = correction_result.final_reasoning_valid
            failure_type = correction_result.final_failure_type

            if correction_result.corrected:
                logger.info(
                    f"Self-correction succeeded after {correction_result.total_attempts} attempts"
                )
            else:
                logger.warning(
                    f"Self-correction failed after {correction_result.total_attempts} attempts"
                )

            knowledge_gap = self._analyze_gap(query, route.intent, normalized_query) if failure_type else None
        else:
            # Initial attempt passed, use as-is
            answer = initial_answer
            grounded = initial_grounded
            failure_type = initial_failure_type
            knowledge_gap = None

        # Final hard gate: if reasoning correction still failed, refuse
        if correction_result is not None and not correction_result.final_reasoning_valid:
            answer = "Insufficient data."
            grounded = True
            failure_type = correction_result.final_failure_type or FailureType.REASONING_REJECT
            knowledge_gap = self._analyze_gap(query, route.intent, normalized_query)

        elapsed_ms = int((time.perf_counter() - t0) * 1000)

        # Extract retry metrics if self-correction was used
        retry_attempts = 0
        corrected = False
        if correction_result is not None:
            retry_attempts = correction_result.total_attempts - 1  # Subtract initial attempt
            corrected = correction_result.corrected

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
            retry_attempts=retry_attempts,
            corrected=corrected,
        )

    def close(self) -> None:
        """No-op close method for CI compatibility."""
        return None
