from __future__ import annotations

from app.config import THRESHOLDS_BY_INTENT, TOP_K
from app.models import RetrievalHit
from events.emitter import emit
from retrieval.faiss_index import FaissIndex


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

    def _emit_retrieval_debug(self, query_id: str, query: str, hits: list[RetrievalHit]) -> None:
        if not query_id:
            return

        emit(
            "retrieval_debug",
            {
                "query_id": query_id,
                "query": query,
                "top_hits": [
                    {"source": hit.source, "score": hit.score}
                    for hit in hits[:10]
                ],
            },
        )

    def retrieve(
        self,
        query_vec,
        intent: str,
        query: str = "",
        query_id: str = "",
    ) -> list[RetrievalHit]:
        if intent == "uncertain":
            raw_hits: list[RetrievalHit] = []
            blended: list[RetrievalHit] = []

            for route_intent in ("cv", "eco", "general"):
                index = self.indexes.get(route_intent)
                if index is None:
                    continue

                route_hits = index.search(query_vec, TOP_K * 2)
                raw_hits.extend(route_hits)
                blended.extend(self._normalize_and_filter(route_hits, route_intent))

            raw_hits.sort(key=lambda hit: hit.score, reverse=True)
            self._emit_retrieval_debug(query_id, query, raw_hits)
            blended.sort(key=lambda hit: hit.score, reverse=True)
            return self._dedupe(blended)[:TOP_K]

        index = self.indexes.get(intent)
        if index is None:
            self._emit_retrieval_debug(query_id, query, [])
            return []

        raw_hits = index.search(query_vec, TOP_K * 2)
        self._emit_retrieval_debug(query_id, query, raw_hits)

        hits = self._normalize_and_filter(raw_hits, intent)
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return self._dedupe(hits)[:TOP_K]
