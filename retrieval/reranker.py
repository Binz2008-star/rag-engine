from __future__ import annotations

import numpy as np
from app.models import RetrievalHit


class Reranker:
    def __init__(self, embed_fn):
        self.embed_fn = embed_fn

    def rerank(self, hits: list[RetrievalHit], query: str, top_k: int) -> list[RetrievalHit]:
        if not hits or len(hits) <= 1:
            return hits[:top_k]

        texts = [query] + [h.text for h in hits]
        embeddings = self.embed_fn(texts)

        query_emb = embeddings[0]
        hit_embs = embeddings[1:]

        scores = []
        for i, hit_emb in enumerate(hit_embs):
            sim = float(np.dot(query_emb, hit_emb) /
                       (np.linalg.norm(query_emb) * np.linalg.norm(hit_emb) + 1e-8))
            scores.append((sim, hits[i]))

        scores.sort(key=lambda x: x[0], reverse=True)

        reranked = []
        for sim, hit in scores[:top_k]:
            hit.score = sim
            reranked.append(hit)

        return reranked
