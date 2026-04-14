from sentence_transformers import CrossEncoder
from typing import List, Any


class CrossReranker:
    """Cross-encoder reranker for semantic relevance scoring."""

    def __init__(self):
        self.model = CrossEncoder("cross-encoder/ms-marco-MiniLM-L-6-v2")

    def rerank(self, query: str, candidates: List[Any]) -> List[Any]:
        """
        Rerank candidates based on query relevance using cross-encoder.

        Args:
            query: Search query string
            candidates: List of candidate objects with .chunk.text attribute

        Returns:
            Ranked list of candidates in descending relevance order.
            Original scores are preserved (order-only rerank).
        """
        if not candidates:
            return candidates

        pairs = [(query, c.chunk.text) for c in candidates]
        scores = self.model.predict(pairs)

        ranked = sorted(
            zip(candidates, scores),
            key=lambda x: x[1],
            reverse=True
        )

        return [c for c, _ in ranked]
