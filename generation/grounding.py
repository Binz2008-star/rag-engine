from __future__ import annotations

import numpy as np

from app.models import RetrievalHit


def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def check_grounding(answer: str, hits: list[RetrievalHit], embed_fn, threshold: float = 0.72) -> bool:
    if not hits or answer.strip() == "Insufficient data.":
        return True

    context = " ".join(hit.text for hit in hits)
    ctx_emb = embed_fn([context])[0]
    claims = [segment for segment in answer.split(".") if len(segment.split()) > 4][:2]

    for claim in claims:
        claim_emb = embed_fn([claim])[0]
        if cosine(claim_emb, ctx_emb) < threshold:
            return False

    return True
