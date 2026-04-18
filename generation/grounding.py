from __future__ import annotations

import re
import numpy as np
from app.models import RetrievalHit


def cosine(a, b):
    return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))


def _sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+", text.strip())
    return [p.strip() for p in parts if len(p.strip()) > 0]


def check_grounding(answer: str, hits: list[RetrievalHit], embed_fn, threshold: float = 0.58) -> bool:
    if not hits:
        return True

    normalized = answer.strip().lower()
    if normalized.startswith("insufficient data"):
        return True

    answer_sentences = _sentences(answer)
    if not answer_sentences:
        return True

    candidate_sentences: list[str] = []
    for hit in hits[:2]:
        candidate_sentences.extend(_sentences(hit.text))

    if not candidate_sentences:
        return True

    all_texts = answer_sentences + candidate_sentences
    embs = embed_fn(all_texts)

    answer_embs = embs[: len(answer_sentences)]
    cand_embs = embs[len(answer_sentences) :]

    for a_emb in answer_embs:
        best = max(cosine(a_emb, c_emb) for c_emb in cand_embs)
        if best < threshold:
            return False

    return True
