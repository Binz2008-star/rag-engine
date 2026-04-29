from __future__ import annotations

import logging

import numpy as np
from app.models import RetrievalHit

log = logging.getLogger(__name__)


class Reranker:
    def __init__(self, embed_fn):
        self.embed_fn = embed_fn

    def rerank(self, hits: list[RetrievalHit], query: str, top_k: int) -> list[RetrievalHit]:
        if not hits or len(hits) <= 1:
            return hits[:top_k]

        texts = [query] + [h.text for h in hits]
        log.info("rerank: embedding %d texts (1 query + %d hits)", len(texts), len(hits))
        embeddings = self.embed_fn(texts)

        query_emb = embeddings[0]
        hit_embs = embeddings[1:]
        log.info(
            "rerank: query_norm=%.4f embed_shape=%s",
            float(np.linalg.norm(query_emb)), embeddings.shape,
        )

        scores = []
        for i, hit_emb in enumerate(hit_embs):
            denom = np.linalg.norm(query_emb) * np.linalg.norm(hit_emb) + 1e-8
            sim = float(np.dot(query_emb, hit_emb) / denom)
            scores.append((sim, hits[i]))

        scores.sort(key=lambda x: x[0], reverse=True)

        reranked = []
        for sim, hit in scores[:top_k]:
            hit.score = sim
            reranked.append(hit)

        log.info(
            "rerank: top_score=%.4f bottom_score=%.4f returned=%d",
            reranked[0].score if reranked else 0.0,
            reranked[-1].score if reranked else 0.0,
            len(reranked),
        )
        return reranked
