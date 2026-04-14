"""Vector store - FAISS index management with metadata."""

from __future__ import annotations

import hashlib
import json
import logging
from pathlib import Path
from typing import List

import faiss
import numpy as np

from app.config import (
    DATA_HASH_PATH,
    DATA_RAW_DIR,
    FAISS_INDEX_PATH,
    METADATA_PATH,
    STORAGE_DIR,
    SUPPORTED_EXTENSIONS,
)
from app.models import Chunk

logger = logging.getLogger(__name__)


class VectorStore:
    """FAISS-based vector store with metadata."""

    def __init__(self) -> None:
        self.index: faiss.Index | None = None
        self.chunks: List[Chunk] = []
        self.dim: int = 0

    def build(self, chunks: List[Chunk], embeddings: np.ndarray) -> None:
        """Build a FAISS index from chunks and embeddings."""
        if not chunks:
            raise ValueError("Cannot build vector store with no chunks.")

        if embeddings.ndim != 2:
            raise ValueError(f"Embeddings must be 2D, got shape={embeddings.shape}.")

        if embeddings.shape[0] != len(chunks):
            raise ValueError(
                f"Chunk/embedding count mismatch: {len(chunks)} chunks vs {embeddings.shape[0]} embeddings."
            )

        if embeddings.shape[1] <= 0:
            raise ValueError(f"Invalid embedding dimension: {embeddings.shape[1]}.")

        if not np.isfinite(embeddings).all():
            raise ValueError("Embeddings contain NaN or Inf values.")

        embeddings = self._normalize_rows(embeddings.astype(np.float32, copy=False))

        self.chunks = chunks
        self.dim = int(embeddings.shape[1])

        # Inner product on normalized vectors == cosine similarity.
        self.index = faiss.IndexFlatIP(self.dim)
        self.index.add(embeddings)

        logger.info("FAISS index built: %d chunks, dim=%d", len(chunks), self.dim)

    def save(self) -> None:
        """Save FAISS index and metadata to disk."""
        STORAGE_DIR.mkdir(parents=True, exist_ok=True)

        # Save FAISS index
        faiss.write_index(self.index, str(FAISS_INDEX_PATH))

        # Save metadata
        metadata = [
            {
                "chunk_id": c.chunk_id,
                "source": c.source,
                "text": c.text,
                "path": c.path,
                "doc_type": c.doc_type,
                "offset": c.offset,
            }
            for c in self.chunks
        ]
        METADATA_PATH.write_text(json.dumps(metadata, ensure_ascii=False), encoding="utf-8")

        logger.info(f"Saved {len(self.chunks)} chunks to {STORAGE_DIR}")

    def load(self) -> None:
        """Load FAISS index and metadata from disk."""
        self.index = faiss.read_index(str(FAISS_INDEX_PATH))
        metadata = json.loads(METADATA_PATH.read_text(encoding="utf-8"))

        self.chunks = [
            Chunk(
                chunk_id=m["chunk_id"],
                source=m["source"],
                text=m["text"],
                path=m["path"],
                doc_type=m["doc_type"],
                offset=m["offset"],
            )
            for m in metadata
        ]

        self.dim = self.index.d

        if self.index.ntotal != len(self.chunks):
            raise ValueError("Corrupt cache: chunk/index count mismatch")

        logger.info(f"Loaded {len(self.chunks)} chunks from FAISS index")

    def search(self, query_embedding: np.ndarray, top_k: int = 4) -> List[tuple[Chunk, float]]:
        """Search for nearest chunks by cosine similarity."""
        if self.index is None or self.index.ntotal == 0:
            return []

        query = np.asarray(query_embedding, dtype=np.float32)

        if query.ndim == 1:
            query = query.reshape(1, -1)
        elif query.ndim != 2 or query.shape[0] != 1:
            raise ValueError(f"Query embedding must have shape (dim,) or (1, dim), got {query.shape}")

        if query.shape[1] != self.dim:
            raise ValueError(f"Query dimension mismatch: expected {self.dim}, got {query.shape[1]}")

        if not np.isfinite(query).all():
            raise ValueError("Query embedding contains NaN or Inf values.")

        query = self._normalize_rows(query)

        top_k = min(max(1, top_k), self.index.ntotal)
        scores, indices = self.index.search(query, top_k)

        results: List[tuple[Chunk, float]] = []
        for idx, score in zip(indices[0], scores[0]):
            if idx >= 0:
                results.append((self.chunks[idx], float(score)))

        return results

    def compute_data_hash(self, folder: Path) -> str:
        """Compute hash of all supported files in folder."""
        hasher = hashlib.md5()
        for path in sorted(folder.rglob("*")):
            if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS:
                try:
                    hasher.update(path.read_bytes())
                except Exception:
                    pass
        return hasher.hexdigest()

    def is_cache_valid(self) -> bool:
        """Check if cached index matches current data."""
        if not (FAISS_INDEX_PATH.exists() and METADATA_PATH.exists() and DATA_HASH_PATH.exists()):
            return False

        current_hash = self.compute_data_hash(DATA_RAW_DIR)
        cached_hash = DATA_HASH_PATH.read_text().strip()

        return current_hash == cached_hash

    def save_data_hash(self) -> None:
        """Save the current raw-data hash for cache validation."""
        current_hash = self.compute_data_hash(DATA_RAW_DIR)
        DATA_HASH_PATH.write_text(current_hash, encoding="utf-8")

    @staticmethod
    def _normalize_rows(arr: np.ndarray) -> np.ndarray:
        """L2-normalize rows safely."""
        norms = np.linalg.norm(arr, axis=1, keepdims=True)
        norms = np.where(norms == 0.0, 1.0, norms)
        return arr / norms
