from __future__ import annotations

import logging

from app.bm25_index import BM25Index
from app.config import THRESHOLDS_BY_INTENT, TOP_K
from app.models import RetrievalHit
from retrieval.faiss_index import FaissIndex
from router.features import extract_hints

logger = logging.getLogger(__name__)

# RRF constant — standard value from the original RRF paper.
_RRF_K = 60


def _rrf_merge(
    dense_hits: list[RetrievalHit],
    sparse_results: list[tuple],
    k: int = _RRF_K,
) -> list[RetrievalHit]:
    """Reciprocal Rank Fusion of dense (FAISS) and sparse (BM25) results.

    Each result list contributes ``1 / (k + rank)`` for every chunk it
    contains. The merged scores are used only for ordering; the final
    ``RetrievalHit.score`` is set to the RRF score so downstream
    threshold filtering still works on a comparable [0, 1] scale after
    normalisation.
    """
    scores: dict[str, float] = {}
    hit_by_id: dict[str, RetrievalHit] = {}

    for rank, hit in enumerate(dense_hits):
        scores[hit.chunk_id] = scores.get(hit.chunk_id, 0.0) + 1.0 / (k + rank)
        hit_by_id[hit.chunk_id] = hit

    for rank, (chunk, _bm25_score) in enumerate(sparse_results):
        cid = chunk.chunk_id
        scores[cid] = scores.get(cid, 0.0) + 1.0 / (k + rank)
        if cid not in hit_by_id:
            hit_by_id[cid] = RetrievalHit(
                chunk_id=chunk.chunk_id,
                source=chunk.source,
                text=chunk.text,
                score=0.0,
                path=chunk.path,
                doc_type=chunk.doc_type,
            )

    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)

    # Normalise RRF scores to [0, 1] so downstream threshold filters
    # (calibrated for FAISS-scale scores) remain meaningful.
    max_score = merged[0][1] if merged else 1.0
    min_score = merged[-1][1] if len(merged) > 1 else 0.0
    score_range = max_score - min_score

    results: list[RetrievalHit] = []
    for cid, rrf_score in merged:
        hit = hit_by_id[cid]
        if score_range > 0:
            hit.score = (rrf_score - min_score) / score_range
        else:
            hit.score = 1.0
        results.append(hit)

    return results


class MultiRetriever:
    def __init__(self, indexes: dict[str, FaissIndex]):
        self.indexes = indexes
        self.version = "hybrid_bm25_faiss_v1"

        # Build per-intent BM25 indexes from the same chunks used by FAISS.
        self._bm25: dict[str, BM25Index] = {}
        for name, faiss_idx in indexes.items():
            if faiss_idx.chunks:
                bm25 = BM25Index()
                bm25.build(faiss_idx.chunks)
                self._bm25[name] = bm25
                logger.info(
                    "BM25 index built for '%s': %d chunks", name, len(faiss_idx.chunks)
                )

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

    def _hybrid_search(self, query_vec, query: str, intent: str, fetch_k: int) -> list[RetrievalHit]:
        """Run dense (FAISS) + sparse (BM25) search and merge with RRF."""
        idx = self.indexes.get(intent)
        if idx is None:
            return []

        # Dense retrieval
        dense_hits = idx.search(query_vec, fetch_k)

        # Sparse retrieval
        bm25 = self._bm25.get(intent)
        sparse_results = bm25.search(query, fetch_k) if bm25 else []

        if not sparse_results:
            return dense_hits

        return _rrf_merge(dense_hits, sparse_results)

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
                merged = self._hybrid_search(query_vec, query, route_intent, TOP_K * 3)
                normalized = self._normalize_and_filter(merged, route_intent)
                blended.extend(normalized)

            blended = self._apply_weighted_blending(blended, weights)
            blended.sort(key=lambda x: x.score, reverse=True)
            return self._dedupe(blended)[:TOP_K]

        merged = self._hybrid_search(query_vec, query, intent, TOP_K * 3)
        hits = self._normalize_and_filter(merged, intent)
        hits.sort(key=lambda x: x.score, reverse=True)
        return self._dedupe(hits)[:TOP_K]
