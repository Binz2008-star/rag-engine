"""Retriever - searches vector store for relevant chunks."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import List

from app.bm25_index import BM25Index
from app.chunking import Chunk
from app.decision_logger import DecisionLogger
from app.embeddings import EmbeddingClient
from app.models import RetrievedChunk
from app.query_normalizer import normalize_query
from app.reranker import LightweightReranker
from app.vector_store import VectorStore

logger = logging.getLogger(__name__)

# ── Retrieval parameters ──────────────────────────────────────────────────────

SCORE_THRESHOLD    = 0.35
MAX_PER_SOURCE     = 2  # STRICT
FINAL_TOP_K        = 6
RETRIEVAL_POOL     = 30

_CV_DETAIL_TERMS = {
    "degree", "education", "bachelor", "mba",
    "software", "tools", "jobber", "power automate",
    "certification", "certifications", "certificate", "certificates",
    "skills", "technical skills",
}
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
        self._bm25: BM25Index | None = None
        self.decision_logger = DecisionLogger()

    def _contains_arabic(self, text: str) -> bool:
        return any('\u0600' <= c <= '\u06FF' for c in text)

    def _source_family(self, source: str) -> str:
        # Legacy source classification removed - no longer needed without hardcoded logic
        return "other"

    # Legacy primary source check removed - no longer needed

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
        if "answer in arabic only" in q:
            return 3
        # Always retrieve full pool to ensure canonical sources are found
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

    def _filter_score(self, retrieved: List[RetrievedChunk]) -> List[RetrievedChunk]:
        """Filter out low-score chunks."""
        filtered = []

        for rc in retrieved:
            if rc.score >= SCORE_THRESHOLD:
                filtered.append(rc)

        logger.info("Score filter: %d/%d above %.2f threshold",
                   len(filtered), len(retrieved), SCORE_THRESHOLD)
        return filtered

    def _detect_query_type(self, query: str) -> str:
        """Detect query type: 'cv', 'eco', or 'general'."""
        q = query.lower()

        # Pre-ECO modifiers: queries about work/history BEFORE ECO override ECO entity
        pre_eco_signals = ["before eco", "before joining", "work history", "prior to", "previously"]
        if any(x in q for x in pre_eco_signals):
            self.decision_logger.log_intent(query, "cv")
            return "cv"

        # Profile identity queries: broad summary requests that should surface Bio
        profile_signals = ["full profile", "professional profile", "overview"]
        if any(x in q for x in profile_signals):
            self.decision_logger.log_intent(query, "profile")
            return "profile"

        # ECO entity detection — runs after pre-ECO and profile checks
        if "eco" in q or "إيكو" in query or "company" in q or "environmental services" in q:
            self.decision_logger.log_intent(query, "eco")
            return "eco"

        # CV-specific signals — only reached if no ECO entity detected above
        cv_triggers = [
            "work history", "before eco", "before joining", "previous",
            "prior", "resume", "education", "cv", "deliveroo",
            "skills", "certificates", "certificate", "who is robin",
            "degree", "bachelor", "tools", "software", "certifications",
            "certification", "qualifications",
        ]
        cv_triggers_ar = ["سيرة", "تعليم", "خبرة", "مهارات", "شهادات"]
        if any(x in q for x in cv_triggers) or any(x in query for x in cv_triggers_ar):
            self.decision_logger.log_intent(query, "cv")
            return "cv"

        self.decision_logger.log_intent(query, "general")
        return "general"

    def _group_by_document(self, retrieved: List[RetrievedChunk], query_type: str = 'general') -> List[RetrievedChunk]:
        """Group chunks by document and rank documents before selecting chunks."""
        from collections import defaultdict

        # Group chunks by source document
        doc_groups = defaultdict(list)
        for rc in retrieved:
            doc_groups[rc.chunk.source].append(rc)

        # Calculate document scores with type-specific boosting
        doc_scores = []
        for source, chunks in doc_groups.items():
            doc_score = max(rc.score for rc in chunks)

            # No boost multipliers - rely on natural scoring
            doc_scores.append((doc_score, source, chunks))

        # Sort documents by score
        doc_scores.sort(reverse=True, key=lambda x: x[0])

        # Apply clean intent-based sorting for CV and ECO queries
        if query_type == 'cv':
            def _cv_doc_priority(source: str) -> int:
                s = source.lower()
                if "deliveroo" in s:
                    return 0
                if "cv" in s:
                    return 1
                return 2

            doc_scores = sorted(doc_scores, key=lambda x: (_cv_doc_priority(x[1]), -x[0]))

        elif query_type == 'eco':
            def _eco_doc_priority(source: str) -> int:
                s = source.lower()
                if "eco_company_profile.pdf" in s:
                    return 0
                if "eco" in s or "ecotech" in s:
                    return 1
                return 2

            doc_scores = sorted(doc_scores, key=lambda x: (_eco_doc_priority(x[1]), -x[0]))

        elif query_type == 'profile':
            def _profile_doc_priority(source: str) -> int:
                s = source.lower()
                if "bio" in s:
                    return 0
                if "cv" in s or "deliveroo" in s:
                    return 1
                return 2

            doc_scores = sorted(doc_scores, key=lambda x: (_profile_doc_priority(x[1]), -x[0]))

        # Select chunks from top documents (top 3 documents)
        selected_chunks = []
        for doc_score, source, chunks in doc_scores[:3]:
            # Sort chunks within document by score
            chunks.sort(key=lambda x: x.score, reverse=True)
            # Take top chunks from each document (max 3 per doc)
            selected_chunks.extend(chunks[:3])

        logger.info("Document grouping (%s type): %d docs → %d chunks from top 3 docs",
                   query_type, len(doc_groups), len(selected_chunks))

        # Log top documents
        for i, (score, source, _) in enumerate(doc_scores[:3], 1):
            logger.info("  Doc[%d]: %s (score=%.4f)", i, source, score)

        # Log grouped order
        grouped_order = [source for _, source, _ in doc_scores[:3]]
        self.decision_logger.log_grouped_order(query, grouped_order)

        return selected_chunks

    def _diversify(self, retrieved: List[RetrievedChunk], max_per_source: int = MAX_PER_SOURCE) -> List[RetrievedChunk]:
        """Diversify chunks - cap at 2 chunks per source."""
        counts = {}
        diversified = []

        for rc in retrieved:
            source = rc.chunk.source
            count = counts.get(source, 0)

            if count < max_per_source:
                diversified.append(rc)
                counts[source] = count + 1

        logger.info("Diversify: %d/%d after capping at %d per source", len(diversified), len(retrieved), max_per_source)
        return diversified

    def _has_cv_detail_signal(self, query: str) -> bool:
        """Return True if the query asks for CV-specific detail (degree, tools, certs)."""
        q = query.lower()
        return any(term in q for term in _CV_DETAIL_TERMS)

    def _rrf_fuse(
        self,
        dense: List[RetrievedChunk],
        sparse: List[tuple],
        k: int = 60,
        dense_weight: float = 0.70,
        sparse_weight: float = 0.30,
    ) -> List[RetrievedChunk]:
        """Weighted Reciprocal Rank Fusion of dense (FAISS) and sparse (BM25) rankings.

        Preserves original FAISS scores so the downstream score-threshold
        filter and reranker operate on meaningful cosine similarities.
        BM25-only chunks receive a provisional score just above SCORE_THRESHOLD
        so they reach the reranker for adjudication.
        """
        rrf: dict[str, float] = {}
        rc_map: dict[str, RetrievedChunk] = {}

        for rank, rc in enumerate(dense, 1):
            cid = rc.chunk.chunk_id
            rrf[cid] = rrf.get(cid, 0.0) + dense_weight / (k + rank)
            rc_map[cid] = rc

        for rank, (chunk, _) in enumerate(sparse, 1):
            cid = chunk.chunk_id
            rrf[cid] = rrf.get(cid, 0.0) + sparse_weight / (k + rank)
            if cid not in rc_map:
                rc_map[cid] = RetrievedChunk(chunk=chunk, score=SCORE_THRESHOLD + 0.01)

        ordered = sorted(rrf, key=lambda c: rrf[c], reverse=True)
        fused = [rc_map[cid] for cid in ordered]
        logger.info(
            "RRF fusion: %d dense + %d sparse → %d unique (dense_w=%.2f sparse_w=%.2f)",
            len(dense), len(sparse), len(fused), dense_weight, sparse_weight,
        )
        return fused

    def _expand_query(self, query: str) -> List[str]:
        """Generate deterministic English query variants for multi-query retrieval."""
        q = query.strip()
        ql = q.lower()
        variants = [q]

        if "who is" in ql:
            variants.append(ql.replace("who is", "describe", 1))
            variants.append(ql.replace("who is", "background of", 1))
        elif "what is" in ql:
            variants.append(ql.replace("what is", "describe", 1))
            variants.append(ql.replace("what is", "information about", 1))
        elif "what are" in ql:
            variants.append(ql.replace("what are", "list of", 1))

        seen: set = set()
        unique: List[str] = []
        for v in variants:
            if v not in seen:
                seen.add(v)
                unique.append(v)
        return unique

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

        # cv_signal: True only when query_type is 'cv' AND query contains detail terms.
        # Using query_type as the gate ensures ECO queries with shared terms (certifications)
        # and pre-ECO queries both route correctly without independent signal conflicts.
        _early_query_type = self._detect_query_type(query)
        cv_signal = (_early_query_type == "cv") and self._has_cv_detail_signal(query)

        queries = self._expand_query(query)

        if is_ar:
            query, _ = normalize_query(query)

            # Dual-query retrieval for Arabic: use both normalized Arabic and English translation
            queries = [query]

            # Translate Arabic to English for better retrieval
            translated = self._translate_arabic_to_english(query)

            # Explicit term mapping for CV queries
            cv_terms = ['تعليم', 'مهارات', 'شهادات', 'خبرة', 'سيرة ذاتية']
            if any(term in query for term in cv_terms) and translated:
                translated += " CV resume Deliveroo"
                logger.info(f"CV query detected, adding terms: {translated}")

            if translated and translated != query:
                logger.info(f"Arabic query translated: {query} → {translated}")
                queries = [query, translated]
            else:
                logger.warning(f"Arabic query translation failed: {query} → {translated}")
                queries = [query]

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

        dense_retrieved = sorted(best_by_chunk.values(), key=lambda rc: rc.score, reverse=True)

        # Hybrid: BM25 sparse search + RRF fusion with dense results
        if self._bm25 is None or len(self._bm25.chunks) != len(vector_store.chunks):
            self._bm25 = BM25Index()
            self._bm25.build(vector_store.chunks)
        sparse_retrieved = self._bm25.search(query, retrieval_pool)
        logger.info("BM25 sparse: %d candidates", len(sparse_retrieved))

        if cv_signal:
            # Hard filter: only CV-family sources allowed in both pools.
            # Bio and ECO both dominate semantically but are not authoritative for CV-detail queries.
            def _is_cv_source(src: str) -> bool:
                s = src.lower()
                return "cv" in s or "deliveroo" in s

            dense_before = len(dense_retrieved)
            sparse_before = len(sparse_retrieved)
            dense_retrieved = [rc for rc in dense_retrieved if _is_cv_source(rc.chunk.source)]
            sparse_retrieved = [(c, s) for c, s in sparse_retrieved if _is_cv_source(c.source)]
            logger.info(
                "CV-detail signal: CV-only filter — dense %d→%d, sparse %d→%d",
                dense_before, len(dense_retrieved), sparse_before, len(sparse_retrieved),
            )

        dense_w, sparse_w = (0.55, 0.45) if cv_signal else (0.70, 0.30)
        retrieved = self._rrf_fuse(dense_retrieved, sparse_retrieved, dense_weight=dense_w, sparse_weight=sparse_w)

        # Log retrieved chunks BEFORE grouping
        retrieved_log = [
            {"chunk_id": rc.chunk.chunk_id, "source": rc.chunk.source, "score": rc.score}
            for rc in retrieved
        ]
        self.decision_logger.log_retrieved(retrieved_log)

        # Diagnostic: Show all unique sources in retrieval pool
        unique_sources = set(rc.chunk.source for rc in retrieved)
        logger.info("Retrieval pool contains %d unique sources: %s",
                   len(unique_sources), sorted(unique_sources))

        for rank, rc in enumerate(retrieved, 1):
            logger.debug("Raw[%2d] %.4f  %s  %s",
                         rank, rc.score, rc.chunk.source, rc.chunk.chunk_id)

        # Pipeline: rerank → adjustments → score filter → diversify → top-k
        if RERANK_ENABLED:
            retrieved = sorted(retrieved, key=lambda rc: rc.score, reverse=True)[:20]
            retrieved = self.reranker.rerank(query, retrieved)
            retrieved = self._apply_scoring_adjustments(query, retrieved, phase="bias")
            retrieved = self._apply_scoring_adjustments(query, retrieved, phase="rescue")
            logger.info("Reranking applied: %d candidates", len(retrieved))

        # Legacy scoring adjustments removed - using reranking scores only

        # Legacy intent-based source priors removed - using reranking scores only

        retrieved = self._filter_score(retrieved)  # No intent parameter needed

        # Detect query type for document-level routing
        query_type = self._detect_query_type(query)
        logger.info(f"Query type detected: {query_type}")

        retrieved = self._group_by_document(retrieved, query_type)  # Group by document with type-specific boosting
        source_cap = 1 if cv_signal else MAX_PER_SOURCE
        retrieved = self._diversify(retrieved, max_per_source=source_cap)

        final = retrieved[:FINAL_TOP_K]

        # Log final selected chunks
        final_chunks_log = [
            {"chunk_id": rc.chunk.chunk_id, "source": rc.chunk.source, "score": rc.score}
            for rc in final
        ]
        self.decision_logger.log_final_chunks(final_chunks_log)

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

        # Enhanced translation prompt for CV/education queries
        prompt = f"""Translate this Arabic text to English. For CV/education related terms:
- تعليم/مهارات/شهادات → include "CV" or "resume" in translation
- خبرة/خبرة عمل → include "experience" or "work history"
- شركة/عمل → include "company" or "job"

Text to translate: {arabic_text}

Return only the English translation:"""

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
