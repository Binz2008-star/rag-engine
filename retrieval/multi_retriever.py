from __future__ import annotations

from app.config import THRESHOLDS_BY_INTENT, TOP_K
from app.models import RetrievalHit
from retrieval.faiss_index import FaissIndex
from router.features import extract_hints


class MultiRetriever:
    def __init__(self, indexes: dict[str, FaissIndex]):
        self.indexes = indexes
        self.version = "faiss_hnsw_v2"

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
            return self._dedupe(blended)[:TOP_K]

        idx = self.indexes.get(intent)
        if idx is None:
            return []

        hits = self._normalize_and_filter(idx.search(query_vec, TOP_K * 3), intent)
        hits.sort(key=lambda x: x.score, reverse=True)
        return self._dedupe(hits)[:TOP_K]
