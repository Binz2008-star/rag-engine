from __future__ import annotations

import logging
from collections import defaultdict
from typing import TYPE_CHECKING

from app.bm25_index import BM25Index
from app.config import THRESHOLDS_BY_INTENT, TOP_K
from app.models import RetrievalHit
from retrieval.faiss_index import FaissIndex
from router.features import extract_hints

if TYPE_CHECKING:
    from app.models import Chunk

logger = logging.getLogger(__name__)


class MultiRetriever:
    def __init__(self, indexes: dict[str, FaissIndex], bm25_index: BM25Index | None = None):
        self.indexes = indexes
        self.bm25_index = bm25_index
        self.version = "faiss_hnsw_v2_hybrid"

        # RRF configuration
        self.rrf_k = 60
        self.dense_weight = 0.70
        self.sparse_weight = 0.30

        # Source diversity limit
        self.max_per_source = 2

    def _normalize_and_filter(self, hits: list[RetrievalHit], intent: str) -> list[RetrievalHit]:
        threshold = THRESHOLDS_BY_INTENT.get(intent, 0.35)
        normalized: list[RetrievalHit] = []

        for hit in hits:
            if hit.score < threshold:
                continue
            hit.score = max(0.0, min(1.0, (hit.score - threshold) / max(1e-8, 1.0 - threshold)))
            normalized.append(hit)

        return normalized

    def _dedupe(self, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        seen: set[str] = set()
        unique: list[RetrievalHit] = []

        for hit in hits:
            if hit.chunk_id in seen:
                continue
            seen.add(hit.chunk_id)
            unique.append(hit)

        return unique

    def _apply_weighted_blending(self, hits: list[RetrievalHit], weights: dict[str, float]) -> list[RetrievalHit]:
        for hit in hits:
            doc_intent = hit.doc_type
            weight = weights.get(doc_intent, 0.35)
            hit.score = hit.score * weight
        return hits

    def _rrf_fuse(
        self,
        dense: list[RetrievalHit],
        sparse: list[tuple[Chunk, float]],
    ) -> list[RetrievalHit]:
        """
        Reciprocal Rank Fusion of dense (FAISS) and sparse (BM25) rankings.

        Downstream gates (e.g. ``hits[0].score < 0.20`` in app.pipeline) expect
        ``hit.score`` to be a [0, 1] similarity-like value. Raw RRF scores are
        unbounded and depend on rrf_k / weights, so we min-max normalize the
        fused ranking back into [0, 1] before returning. This preserves the
        relative ordering produced by RRF while keeping score semantics stable
        for callers that pre-existed BM25 fusion.
        """
        rrf: dict[str, float] = {}
        rc_map: dict[str, RetrievalHit] = {}

        for rank, rc in enumerate(dense, 1):
            cid = rc.chunk_id
            rrf[cid] = rrf.get(cid, 0.0) + self.dense_weight / (self.rrf_k + rank)
            rc_map[cid] = rc

        for rank, (chunk, score) in enumerate(sparse, 1):
            cid = chunk.chunk_id
            rrf[cid] = rrf.get(cid, 0.0) + self.sparse_weight / (self.rrf_k + rank)
            if cid not in rc_map:
                # Create RetrievalHit for BM25-only results
                rc_map[cid] = RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    text=chunk.text,
                    score=0.35,  # Just above threshold
                    path=chunk.path,
                    doc_type=chunk.doc_type,
                )

        ordered = sorted(rrf, key=lambda c: rrf[c], reverse=True)

        # Normalize RRF scores to [0, 1] so downstream score gates still work.
        if ordered:
            top_score = rrf[ordered[0]]
            if top_score > 0:
                for cid in ordered:
                    rc_map[cid].score = max(0.0, min(1.0, rrf[cid] / top_score))

        fused = [rc_map[cid] for cid in ordered]
        logger.info(
            "RRF fusion: %d dense + %d sparse → %d unique",
            len(dense), len(sparse), len(fused),
        )
        return fused

    def _enforce_source_diversity(self, hits: list[RetrievalHit]) -> list[RetrievalHit]:
        """Diversify chunks - cap at max_per_source per source."""
        counts: dict[str, int] = {}
        diversified: list[RetrievalHit] = []

        for hit in hits:
            source = hit.source
            count = counts.get(source, 0)

            if count < self.max_per_source:
                diversified.append(hit)
                counts[source] = count + 1

        logger.info(
            "Source diversity: %d/%d after capping at %d per source",
            len(diversified), len(hits), self.max_per_source,
        )
        return diversified

    def retrieve(self, query_vec, intent: str, query: str) -> list[RetrievalHit]:
        if intent == "uncertain":
            eco_hint, cv_hint = extract_hints(query)

            if eco_hint and not cv_hint:
                weights = {"eco": 1.0, "general": 0.35, "cv": 0.15}
            elif cv_hint and not eco_hint:
                weights = {"cv": 1.0, "general": 0.35, "eco": 0.15}
            else:
                weights = {"general": 1.0, "eco": 0.35, "cv": 0.35}

            blended: list[RetrievalHit] = []
            for route_intent in ("cv", "eco", "general"):
                idx = self.indexes.get(route_intent)
                if idx is None:
                    continue
                raw_hits = idx.search(query_vec, TOP_K * 3)
                normalized = self._normalize_and_filter(raw_hits, route_intent)
                blended.extend(normalized)

            blended = self._apply_weighted_blending(blended, weights)
            blended.sort(key=lambda x: x.score, reverse=True)
            blended = self._dedupe(blended)

            # Apply BM25 + RRF if available
            if self.bm25_index and self.bm25_index.chunks:
                sparse_hits = self.bm25_index.search(query, TOP_K * 3)
                blended = self._rrf_fuse(blended, sparse_hits)

            # Apply source diversity
            blended = self._enforce_source_diversity(blended)

            return blended[:TOP_K]

        idx = self.indexes.get(intent)
        if idx is None:
            return []

        # Dense retrieval
        dense_hits = self._normalize_and_filter(idx.search(query_vec, TOP_K * 3), intent)
        dense_hits.sort(key=lambda x: x.score, reverse=True)
        dense_hits = self._dedupe(dense_hits)

        # Apply BM25 + RRF if available
        if self.bm25_index and self.bm25_index.chunks:
            sparse_hits = self.bm25_index.search(query, TOP_K * 3)
            dense_hits = self._rrf_fuse(dense_hits, sparse_hits)

        # Apply source diversity
        dense_hits = self._enforce_source_diversity(dense_hits)

        return dense_hits[:TOP_K]
