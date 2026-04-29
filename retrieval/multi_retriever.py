from __future__ import annotations

import logging

from app.config import THRESHOLDS_BY_INTENT, TOP_K
from app.models import RetrievalHit
from retrieval.faiss_index import FaissIndex
from router.features import extract_hints

log = logging.getLogger(__name__)

# Terms whose presence in a query triggers a small score boost for
# chunks that also contain them.  Improves recall for pricing /
# commercial queries without altering grounding logic.
_PRICING_QUERY_TERMS: frozenset[str] = frozenset({
    "price", "pricing", "cost", "costs", "quote",
    "aed", "grease trap", "grease traps",
    "size a", "size b", "size c", "size d",
    "rate", "rates", "fee", "fees",
})

_PRICING_BOOST = 0.10


class MultiRetriever:
    def __init__(self, indexes: dict[str, FaissIndex]):
        self.indexes = indexes
        self.version = "faiss_hnsw_v2"

    def _normalize_and_filter(self, hits: list[RetrievalHit], intent: str) -> list[RetrievalHit]:
        threshold = THRESHOLDS_BY_INTENT.get(intent, 0.35)
        normalized: list[RetrievalHit] = []

        for hit in hits:
            if hit.score < threshold:
                log.debug(
                    "Dropped hit %s (score=%.4f < threshold=%.4f, intent=%s)",
                    hit.chunk_id, hit.score, threshold, intent,
                )
                continue
            hit.score = max(0.0, min(1.0, (hit.score - threshold) / max(1e-8, 1.0 - threshold)))
            normalized.append(hit)

        log.debug(
            "normalize_and_filter: intent=%s threshold=%.2f in=%d out=%d",
            intent, threshold, len(hits), len(normalized),
        )
        return normalized

    @staticmethod
    def _apply_pricing_boost(
        hits: list[RetrievalHit], query: str,
    ) -> list[RetrievalHit]:
        """Boost chunks containing pricing terms when the query is pricing-related."""
        q = query.lower()
        if not any(term in q for term in _PRICING_QUERY_TERMS):
            return hits
        for hit in hits:
            text_lower = hit.text.lower()
            if any(term in text_lower for term in ("price", "pricing", "aed", "cost")):
                hit.score = min(1.0, hit.score + _PRICING_BOOST)
                log.debug("Pricing boost applied to %s (new score=%.4f)", hit.chunk_id, hit.score)
        return hits

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
        log.debug("retrieve: intent=%s query=%r", intent, query[:80])

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
            blended = self._apply_pricing_boost(blended, query)
            blended.sort(key=lambda x: x.score, reverse=True)
            return self._dedupe(blended)[:TOP_K]

        idx = self.indexes.get(intent)
        if idx is None:
            log.warning("No index for intent=%s", intent)
            return []

        hits = self._normalize_and_filter(idx.search(query_vec, TOP_K * 3), intent)
        hits = self._apply_pricing_boost(hits, query)
        hits.sort(key=lambda x: x.score, reverse=True)
        log.debug(
            "retrieve: intent=%s returning %d hits (top=%.4f)",
            intent, len(hits), hits[0].score if hits else 0.0,
        )
        return self._dedupe(hits)[:TOP_K]
