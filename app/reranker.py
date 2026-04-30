"""Lightweight reranker — multi-signal second-pass scoring.

Combines dense (semantic), sparse (BM25), and phrase-match signals
that arrive on each ``RetrievalHit`` from the hybrid retriever.
Scores are min-max normalised *per signal* before weighting so that
the configured weights are meaningful regardless of raw score ranges.
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import List

from app.config import RERANK_ENABLED
from app.models import RetrievalHit

logger = logging.getLogger(__name__)


def _min_max(values: list[float]) -> tuple[float, float, float]:
    """Return (min, max, range) for a list of floats."""
    if not values:
        return 0.0, 1.0, 1.0
    lo, hi = min(values), max(values)
    return lo, hi, max(hi - lo, 1e-8)


@dataclass(frozen=True)
class RerankBreakdown:
    """Per-hit breakdown of rerank score components (all normalised)."""
    dense: float
    sparse: float
    phrase: float
    final: float


class LightweightReranker:
    """Pipeline-compatible reranker using retriever-provided signals.

    The hybrid retriever stores ``dense_score`` (FAISS cosine) and
    ``sparse_score`` (BM25) on every ``RetrievalHit``.  This reranker
    normalises them independently and combines with a phrase-match
    bonus.  No re-embedding or extra model calls are required.
    """

    def __init__(
        self,
        semantic_weight: float = 0.6,
        bm25_weight: float = 0.3,
        phrase_weight: float = 0.1,
    ) -> None:
        self.semantic_weight = semantic_weight
        self.bm25_weight = bm25_weight
        self.phrase_weight = phrase_weight

    # ------------------------------------------------------------------
    # Pipeline interface — matches Reranker.rerank(hits, query, top_k)
    # ------------------------------------------------------------------

    def rerank(
        self,
        hits: List[RetrievalHit],
        query: str,
        top_k: int,
    ) -> List[RetrievalHit]:
        """Rerank *hits* and return the best *top_k*."""
        if not RERANK_ENABLED or not hits:
            return hits[:top_k]
        if len(hits) <= 1:
            return hits[:top_k]

        normalized_query = self._normalize_text(query)

        # Collect raw signals for batch normalisation.
        raw_dense = [h.dense_score for h in hits]
        raw_sparse = [h.sparse_score for h in hits]

        d_lo, _, d_range = _min_max(raw_dense)
        s_lo, _, s_range = _min_max(raw_sparse)

        scored: list[tuple[RetrievalHit, RerankBreakdown]] = []
        for hit in hits:
            norm_dense = (hit.dense_score - d_lo) / d_range
            norm_sparse = (hit.sparse_score - s_lo) / s_range

            norm_chunk = self._normalize_text(hit.text)
            phrase = self._phrase_bonus(normalized_query, norm_chunk)

            final = (
                self.semantic_weight * norm_dense
                + self.bm25_weight * norm_sparse
                + self.phrase_weight * phrase
            )

            scored.append((hit, RerankBreakdown(
                dense=norm_dense,
                sparse=norm_sparse,
                phrase=phrase,
                final=final,
            )))

        scored.sort(key=lambda x: x[1].final, reverse=True)

        # Debug logging — top results with score breakdowns.
        if scored:
            logger.info("RERANK TOP RESULTS:")
            for i, (h, bd) in enumerate(scored[:5]):
                logger.info(
                    "  %d. score=%.4f (dense=%.3f sparse=%.3f phrase=%.3f) | %s",
                    i + 1, bd.final, bd.dense, bd.sparse, bd.phrase,
                    h.source,
                )

        results = scored[:top_k]
        for hit, bd in results:
            hit.score = bd.final

        return [h for h, _ in results]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize_text(text: str) -> str:
        """Lowercase + collapse whitespace + basic Arabic normalisation."""
        text = re.sub(r"[إأآ]", "ا", text)
        text = text.replace("ى", "ي").replace("ؤ", "و").replace("ئ", "ي")
        text = re.sub(r"[\u064B-\u065F\u0670]", "", text)
        text = text.lower()
        text = re.sub(r"[^\w\s]", " ", text)
        return re.sub(r"\s+", " ", text).strip()

    @staticmethod
    def _phrase_bonus(normalized_query: str, normalized_chunk: str) -> float:
        """1.0 if the full normalised query appears as a substring."""
        if len(normalized_query.split()) < 2:
            return 0.0
        return 1.0 if normalized_query in normalized_chunk else 0.0
