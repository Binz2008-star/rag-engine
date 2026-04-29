from __future__ import annotations

import json
import logging
from pathlib import Path

import faiss
import numpy as np

from app.models import Chunk, RetrievalHit

log = logging.getLogger(__name__)


class IndexMismatchError(RuntimeError):
    """FAISS vector count does not match chunk metadata length."""


class FaissIndex:
    def __init__(self, name: str, dim: int | None = None):
        self.name = name
        self.dim = dim
        self.index: faiss.Index | None = None
        self.chunks: list[Chunk] = []

    def build(self, chunks: list[Chunk]) -> None:
        if not chunks:
            raise ValueError(f"No chunks provided for index {self.name}")
        if chunks[0].embedding is None:
            raise ValueError("Chunks must contain embeddings before building index")

        matrix = np.array([chunk.embedding for chunk in chunks], dtype=np.float32)
        dim = matrix.shape[1]
        self.index = faiss.IndexHNSWFlat(dim, 32)
        self.index.hnsw.efConstruction = 40
        self.index.add(matrix)
        self.dim = dim
        self.chunks = chunks

    def search(self, query_vec: np.ndarray, top_k: int) -> list[RetrievalHit]:
        if self.index is None or not self.chunks:
            return []

        query = query_vec.reshape(1, -1).astype(np.float32)
        scores, indices = self.index.search(query, min(top_k, len(self.chunks)))
        hits: list[RetrievalHit] = []
        n_chunks = len(self.chunks)

        for score, idx in zip(scores[0], indices[0]):
            if idx < 0:
                continue
            int_idx = int(idx)
            if int_idx >= n_chunks:
                log.warning(
                    "FAISS returned index %d but only %d chunks in '%s' "
                    "— skipping (index/metadata mismatch?)",
                    int_idx, n_chunks, self.name,
                )
                continue
            chunk = self.chunks[int_idx]
            hits.append(
                RetrievalHit(
                    chunk_id=chunk.chunk_id,
                    source=chunk.source,
                    text=chunk.text,
                    score=float(score),
                    path=chunk.path,
                    doc_type=chunk.doc_type,
                )
            )

        return hits

    def save(self, out_dir: Path) -> None:
        if self.index is None:
            raise ValueError("Cannot save an empty index")

        out_dir.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(out_dir / f"{self.name}.faiss"))
        meta = [chunk.__dict__ | {"embedding": None} for chunk in self.chunks]
        (out_dir / f"{self.name}.json").write_text(
            json.dumps(meta, ensure_ascii=False),
            encoding="utf-8",
        )

    @classmethod
    def load(cls, name: str, out_dir: Path) -> "FaissIndex":
        instance = cls(name=name)
        instance.index = faiss.read_index(str(out_dir / f"{name}.faiss"))
        meta = json.loads((out_dir / f"{name}.json").read_text(encoding="utf-8"))
        instance.chunks = [Chunk(**row) for row in meta]
        instance.dim = instance.index.d

        n_vectors = instance.index.ntotal
        n_chunks = len(instance.chunks)
        if n_vectors != n_chunks:
            raise IndexMismatchError(
                f"Index '{name}': FAISS has {n_vectors} vectors but "
                f"metadata has {n_chunks} chunks — rebuild with "
                f"scripts/build_indexes.py"
            )
        return instance
