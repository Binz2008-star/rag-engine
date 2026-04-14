"""Lightweight reranker - second-pass scoring after FAISS retrieval."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

from app.config import (
    RERANK_ENABLED,
    RERANK_LEXICAL_WEIGHT,
    RERANK_PHRASE_WEIGHT,
    RERANK_SEMANTIC_WEIGHT,
    RERANK_SOURCE_PRIOR_WEIGHT,
)
from app.models import RetrievedChunk

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RerankBreakdown:
    """Breakdown of rerank score components."""
    semantic: float
    lexical: float
    phrase: float
    source_prior: float
    final: float


class LightweightReranker:
    """Lightweight reranker combining semantic, lexical, phrase, and source signals."""

    def __init__(
        self,
        semantic_weight: float = RERANK_SEMANTIC_WEIGHT,
        lexical_weight: float = RERANK_LEXICAL_WEIGHT,
        phrase_weight: float = RERANK_PHRASE_WEIGHT,
        source_prior_weight: float = RERANK_SOURCE_PRIOR_WEIGHT,
    ) -> None:
        self.semantic_weight = semantic_weight
        self.lexical_weight = lexical_weight
        self.phrase_weight = phrase_weight
        self.source_prior_weight = source_prior_weight

    def rerank(self, query: str, candidates: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """
        Rerank candidates using multi-signal scoring.
        Returns re-sorted list of candidates with updated scores.
        """
        if not RERANK_ENABLED:
            return candidates

        if not candidates:
            return candidates

        # Normalize query for token matching
        normalized_query = self._normalize_text(query)
        query_tokens = self._tokenize(normalized_query)

        # Compute rerank scores
        reranked = []
        for rc in candidates:
            breakdown = self._compute_rerank_score(
                query,
                normalized_query,
                query_tokens,
                rc,
            )
            updated_rc = RetrievedChunk(chunk=rc.chunk, score=breakdown.final)
            reranked.append((updated_rc, breakdown))

            if logger.isEnabledFor(logging.DEBUG):
                logger.debug(
                    "Rerank: %s | semantic=%.3f lexical=%.3f phrase=%.3f source=%.3f final=%.3f",
                    rc.chunk.source[:30],
                    breakdown.semantic,
                    breakdown.lexical,
                    breakdown.phrase,
                    breakdown.source_prior,
                    breakdown.final,
                )

        # Sort by final rerank score
        reranked.sort(key=lambda x: x[1].final, reverse=True)

        # Return updated candidates
        return [rc for rc, _ in reranked]

    def _compute_rerank_score(
        self,
        query: str,
        normalized_query: str,
        query_tokens: set[str],
        rc: RetrievedChunk,
    ) -> RerankBreakdown:
        """Compute rerank score breakdown for a single candidate."""
        # Semantic score (existing FAISS score)
        semantic_score = rc.score

        # Lexical overlap score
        normalized_chunk = self._normalize_text(rc.chunk.text)
        chunk_tokens = self._tokenize(normalized_chunk)
        lexical_score = self._compute_lexical_overlap(query_tokens, chunk_tokens)

        # Phrase match bonus
        phrase_score = self._compute_phrase_bonus(normalized_query, normalized_chunk)

        # Source prior (derived from boost rules)
        source_prior = self._compute_source_prior(rc.chunk.source, query)

        # Final weighted score
        final_score = (
            self.semantic_weight * semantic_score
            + self.lexical_weight * lexical_score
            + self.phrase_weight * phrase_score
            + self.source_prior_weight * source_prior
        )

        return RerankBreakdown(
            semantic=semantic_score,
            lexical=lexical_score,
            phrase=phrase_score,
            source_prior=source_prior,
            final=final_score,
        )

    def _normalize_text(self, text: str) -> str:
        """Normalize text for lexical comparison."""
        # Simple Arabic normalization (without external dependencies)
        text = re.sub(r"[إأآ]", "ا", text)
        text = text.replace("ى", "ي")
        text = text.replace("ؤ", "و")
        text = text.replace("ئ", "ي")
        # Remove diacritics
        text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
        # Lowercase
        text = text.lower()
        # Remove punctuation
        text = re.sub(r"[^\w\s]", " ", text)
        # Collapse whitespace
        text = re.sub(r"\s+", " ", text)
        return text.strip()

    def _tokenize(self, text: str) -> set[str]:
        """Tokenize text into set of meaningful tokens."""
        tokens = text.split()
        # Ignore very short tokens
        return {t for t in tokens if len(t) >= 3}

    def _compute_lexical_overlap(self, query_tokens: set[str], chunk_tokens: set[str]) -> float:
        """Compute normalized token overlap between query and chunk."""
        if not query_tokens:
            return 0.0

        overlap = len(query_tokens & chunk_tokens)
        return overlap / len(query_tokens)

    def _compute_phrase_bonus(self, normalized_query: str, normalized_chunk: str) -> float:
        """Compute phrase match bonus for strong exact normalized phrase matches."""
        if len(normalized_query.split()) < 2:
            return 0.0

        # Check if full normalized query appears in chunk
        if normalized_query in normalized_chunk:
            return 1.0

        return 0.0

    def _compute_source_prior(self, source: str, query: str) -> float:
        """
        Compute source prior based on existing boost rules and query context.
        Returns a small contribution (0.0-0.2 range).
        """
        source_lower = source.lower()
        query_lower = query.lower()

        # Force ECO boost for company-related queries
        if "eco" in query_lower or "company" in query_lower or "services" in query_lower:
            if "eco_company_profile" in source_lower:
                return 0.25  # Strong boost for ECO profile on company queries

        # ECO Company Profile prior
        if "eco" in source_lower or "company_profile" in source_lower:
            return 0.15

        # CV TXT prior
        if "tailored" in source_lower or "deliveroo" in source_lower:
            return 0.1

        return 0.0
