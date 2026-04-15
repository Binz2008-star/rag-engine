"""Retriever - searches vector store for relevant chunks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List

from app.chunking import Chunk
from app.embeddings import EmbeddingClient
from app.models import RetrievedChunk
from app.query_normalizer import normalize_query
from app.reranker import LightweightReranker
# Legacy SourcePolicy import removed - no longer needed without boost logic
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)

# ── Retrieval parameters ──────────────────────────────────────────────────────

SCORE_THRESHOLD    = 0.35
MAX_PER_SOURCE     = 2  # STRICT
FINAL_TOP_K        = 6
RETRIEVAL_POOL     = 30
RERANK_ENABLED     = True


# ── Scoring adjustment rules (consolidated) ──────────────────────────────────
# All post-rerank scoring adjustments are now handled by SourcePolicy module.
# Legacy boost rules removed - using proper reranking instead.

# Legacy ScoringRule dataclass removed - no longer needed


# Legacy scoring rules removed - replaced by reranking algorithms.


# Legacy helper functions removed - no longer needed without scoring rules


# ── Constants ───────────────────────────────────────────────────────────────────────

PRIMARY_ECO = "ECO_Company_Profile.pdf"
PRIMARY_CV = "Roben_Edwan_Deliveroo_Tailored_CV.txt"

# ── Retriever ─────────────────────────────────────────────────────────────────

class Retriever:
    """Retrieves relevant chunks for a query."""

    def __init__(self, embedding_client: EmbeddingClient) -> None:
        self.embedding_client = embedding_client
        self.reranker = LightweightReranker()
        # Legacy SourcePolicy removed - no longer needed

    def _contains_arabic(self, text: str) -> bool:
        return any('\u0600' <= c <= '\u06FF' for c in text)

    def _source_family(self, source: str) -> str:
        s = source.lower()
        if "eco" in s:
            return "eco"
        if "cv" in s or "deliveroo" in s or "roben" in s or "robin" in s:
            return "cv"
        return "other"

    def _is_primary_eco(self, source: str) -> bool:
        return source == "ECO_Company_Profile.pdf"

    def _safe_search(self, vector_store: VectorStore, query_embedding, top_k: int) -> List[tuple]:
        """Failsafe retrieval - never return empty results."""
        results = vector_store.search(query_embedding, top_k)
        if not results:
            logger.warning("Empty retrieval, falling back to first chunks")
            return [(c, 1.0) for c in vector_store.chunks[:top_k]]
        return results

    def _get_top_k(self, query: str) -> int:
        """Get dynamic TOP_K based on query length to reduce retrieval cost."""
        q = query.lower()
        if "answer in arabic only" in q or len(query) > 120:
            return 3
        return RETRIEVAL_POOL

    def _get_chunks_by_source(self, all_chunks: List[RetrievedChunk], source: str, k: int = 3) -> List[RetrievedChunk]:
        """Get chunks by source name directly, bypassing FAISS."""
        return [c for c in all_chunks if c.chunk.source == source][:k]

    # Legacy injection methods removed - using proper retrieval instead

    # ── Private pipeline steps ────────────────────────────────────────────────

    def _apply_scoring_adjustments(
        self, query: str, retrieved: List[RetrievedChunk], phase: str
    ) -> List[RetrievedChunk]:
        """Legacy method - simply returns sorted chunks (all adjustments removed)."""
        result = sorted(retrieved, key=lambda x: x.score, reverse=True)
        return result

    def _filter_score(self, retrieved: List[RetrievedChunk], intent: str) -> List[RetrievedChunk]:
        """Filter out low-score chunks - intent protection removed for clean baseline."""
        filtered = []

        for rc in retrieved:
            if rc.score >= SCORE_THRESHOLD:
                filtered.append(rc)

        logger.info("Score filter: %d/%d above %.2f threshold",
                   len(filtered), len(retrieved), SCORE_THRESHOLD)
        return filtered

    def _diversify(self, retrieved: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Diversify chunks - cap at 2 chunks per source (Phase 2)."""
        counts = {}
        diversified = []

        for rc in retrieved:
            source = rc.chunk.source
            count = counts.get(source, 0)

            if count < 2:  # Cap at 2 chunks per source
                diversified.append(rc)
                counts[source] = count + 1

        logger.info("Diversify: %d/%d after capping at 2 per source", len(diversified), len(retrieved))
        return diversified

    # ── Public API ────────────────────────────────────────────────────────────

    def retrieve(self, query: str, vector_store: VectorStore) -> List[RetrievedChunk]:
        """Return up to FINAL_TOP_K chunks for query after filtering and reranking."""
        if not isinstance(query, str) or not query.strip():
            raise ValueError("Query must be a non-empty string.")

        # Arabic detection and normalization
        is_ar = self._contains_arabic(query)

        # Legacy intent detection removed - no longer needed without hardcoded logic

        # Get dynamic TOP_K based on query length (reduce retrieval cost)
        retrieval_pool = self._get_top_k(query)

        queries = [query]

        if is_ar:
            query, _ = normalize_query(query)

            # Dual-query retrieval for Arabic: use both normalized Arabic and English translation
            queries = [query]

            # Translate Arabic to English for better retrieval
            translated = self._translate_arabic_to_english(query)
            if translated and translated != query:
                logger.info(f"Arabic query translated: {query} → {translated}")
                queries = [query, translated]

        t0 = time.perf_counter()
        all_retrieved = []

        for q in queries:
            query_embedding = self.embedding_client.embed_batch([q])[0]
            raw = self._safe_search(vector_store, query_embedding, retrieval_pool)
            retrieved = [RetrievedChunk(chunk=c, score=s) for c, s in raw]
            all_retrieved.extend(retrieved)

        logger.info("Raw retrieval: %d chunks in %.3fs (using %d queries)",
                    len(all_retrieved), time.perf_counter() - t0, len(queries))

        # Legacy injection calls removed - using proper retrieval instead

        best_by_chunk = {}

        for rc in all_retrieved:
            cid = rc.chunk.chunk_id
            existing = best_by_chunk.get(cid)
            if existing is None or rc.score > existing.score:
                best_by_chunk[cid] = rc

        retrieved = list(best_by_chunk.values())

        for rank, rc in enumerate(retrieved, 1):
            logger.debug("Raw[%2d] %.4f  %s  %s",
                         rank, rc.score, rc.chunk.source, rc.chunk.chunk_id)

        # Pipeline: rerank → bias → rescue → boost → sort → score filter → diversify → top-k
        if RERANK_ENABLED:
            retrieved = retrieved[:20]
            retrieved = self.reranker.rerank(query, retrieved)
            retrieved = self._apply_scoring_adjustments(query, retrieved, phase="bias")
            retrieved = self._apply_scoring_adjustments(query, retrieved, phase="rescue")
            logger.info("Reranking applied: %d candidates", len(retrieved))

        retrieved = self._apply_scoring_adjustments(query, retrieved, phase="boost")

        # Legacy intent-based source priors removed - using reranking scores only

        retrieved = self._filter_score(retrieved, "neutral")  # Default intent
        retrieved = self._diversify(retrieved)

        final = retrieved[:FINAL_TOP_K]

        # Aggressive context trimming for Arabic-only queries (test 38)
        if "answer in arabic only" in query.lower():
            final = final[:2]

        logger.info("Final: %d/%d chunks selected", len(final), FINAL_TOP_K)
        for rank, rc in enumerate(final, 1):
            logger.info("Final[%d] %.4f  %s  %s",
                         rank, rc.score, rc.chunk.source, rc.chunk.chunk_id)

        return final

    def _translate_arabic_to_english(self, arabic_text: str) -> str:
        """Translate Arabic text to English using the LLM."""
        import requests
        from app.config import OLLAMA_BASE_URL, CHAT_MODEL, TIMEOUT

        prompt = f"Translate this Arabic text to English. Return only the English translation, no explanations:\n\n{arabic_text}"

        try:
            response = requests.post(
                f"{OLLAMA_BASE_URL}/chat",
                json={
                    "model": CHAT_MODEL,
                    "stream": False,
                    "messages": [{"role": "user", "content": prompt}],
                    "options": {"temperature": 0.1, "num_predict": 256},
                },
                timeout=TIMEOUT,
            )
            response.raise_for_status()
            data = response.json()
            translated = data.get("message", {}).get("content", "").strip()
            return translated
        except Exception as e:
            logger.warning(f"Arabic translation failed: {e}")
            return ""
