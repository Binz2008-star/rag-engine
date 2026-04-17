"""Corpus-level BM25 index for sparse keyword retrieval (first-stage)."""

from __future__ import annotations

import logging
import math
import re
from typing import Dict, List, Tuple

from app.models import Chunk

logger = logging.getLogger(__name__)


class BM25Index:
    """
    Okapi BM25 index built from corpus chunks.
    Used alongside FAISS dense retrieval in hybrid search.
    """

    K1: float = 1.5  # term-frequency saturation
    B: float = 0.75  # document-length normalisation

    def __init__(self) -> None:
        self.chunks: List[Chunk] = []
        self._doc_tokens: List[List[str]] = []
        self._df: Dict[str, int] = {}
        self._idf: Dict[str, float] = {}
        self._avgdl: float = 0.0
        self._N: int = 0

    # ── Build ─────────────────────────────────────────────────────────────────

    def build(self, chunks: List[Chunk]) -> None:
        """Build index from a list of Chunk objects."""
        self.chunks = list(chunks)
        self._N = len(chunks)
        self._doc_tokens = [self._tokenize(c.text) for c in chunks]

        self._df = {}
        for tokens in self._doc_tokens:
            for term in set(tokens):
                self._df[term] = self._df.get(term, 0) + 1

        total_len = sum(len(t) for t in self._doc_tokens)
        self._avgdl = total_len / self._N if self._N else 1.0

        self._idf = {
            term: math.log((self._N - df + 0.5) / (df + 0.5) + 1.0)
            for term, df in self._df.items()
        }

        logger.info(
            "BM25 index built: %d chunks, vocab=%d, avgdl=%.1f",
            self._N, len(self._df), self._avgdl,
        )

    # ── Search ────────────────────────────────────────────────────────────────

    def search(self, query: str, top_k: int) -> List[Tuple[Chunk, float]]:
        """Return top_k (Chunk, bm25_score) pairs for query."""
        if not self.chunks:
            return []
        q_tokens = self._tokenize(query)
        if not q_tokens:
            return []

        scored: List[Tuple[float, int]] = []
        for i, doc_tokens in enumerate(self._doc_tokens):
            s = self._score(q_tokens, doc_tokens)
            if s > 0.0:
                scored.append((s, i))

        scored.sort(reverse=True)
        return [(self.chunks[i], s) for s, i in scored[:top_k]]

    # ── Internals ─────────────────────────────────────────────────────────────

    def _score(self, q_tokens: List[str], doc_tokens: List[str]) -> float:
        dl = len(doc_tokens)
        if dl == 0:
            return 0.0

        tf_map: Dict[str, int] = {}
        for t in doc_tokens:
            tf_map[t] = tf_map.get(t, 0) + 1

        score = 0.0
        for term in set(q_tokens):
            tf = tf_map.get(term, 0)
            if tf == 0:
                continue
            idf = self._idf.get(term, 0.0)
            tf_norm = tf * (self.K1 + 1) / (
                tf + self.K1 * (1.0 - self.B + self.B * dl / self._avgdl)
            )
            score += idf * tf_norm
        return score

    @staticmethod
    def _tokenize(text: str) -> List[str]:
        text = re.sub(r"[^\w\s]", " ", text.lower())
        return [t for t in text.split() if len(t) >= 3]
