"""Reasoning verifier - validates logical reasoning chains in RAG answers."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from typing import Callable

from app.models import RetrievalHit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ReasoningBreakdown:
    """Breakdown of reasoning verification components."""
    has_premise_support: bool
    has_logical_flow: bool
    avoids_speculation: bool
    has_conclusion_link: bool
    final_score: float


class ReasoningVerifier:
    """Verifies that answers follow logical reasoning from retrieved context."""

    def __init__(
        self,
        premise_threshold: float = 0.5,
        enable_speculation_check: bool = True,
    ) -> None:
        self.premise_threshold = premise_threshold
        self.enable_speculation_check = enable_speculation_check

        # Speculative language patterns that indicate weak reasoning
        self.speculative_patterns = [
            re.compile(r"\blikely\b", re.I),
            re.compile(r"\bprobably\b", re.I),
            re.compile(r"\bit appears\b", re.I),
            re.compile(r"\bit seems\b", re.I),
            re.compile(r"\bmay be\b", re.I),
            re.compile(r"\bmight be\b", re.I),
            re.compile(r"\bpossibly\b", re.I),
            re.compile(r"\bperhaps\b", re.I),
            re.compile(r"\bpresumably\b", re.I),
            re.compile(r"\bapparently\b", re.I),
        ]

        # Logical connector patterns for flow checking
        self.logical_connectors = [
            "because", "since", "therefore", "thus", "hence",
            "consequently", "as a result", "due to", "leads to",
            "causes", "results in", "means that", "indicates"
        ]

    def verify(
        self,
        answer: str,
        hits: list[RetrievalHit],
        embed_fn: Callable[[list[str]], list] | None = None,
    ) -> tuple[bool, ReasoningBreakdown]:
        """
        Verify that the answer follows logical reasoning from context.

        Args:
            answer: Generated answer text
            hits: Retrieved context chunks
            embed_fn: Optional embedding function for semantic similarity

        Returns:
            Tuple of (is_valid, breakdown) where breakdown contains component scores
        """
        if not hits:
            # No context to verify against - accept as valid (will be caught by grounding)
            return True, ReasoningBreakdown(
                has_premise_support=True,
                has_logical_flow=True,
                avoids_speculation=True,
                has_conclusion_link=True,
                final_score=1.0,
            )

        normalized_answer = answer.strip().lower()
        if normalized_answer.startswith("insufficient data"):
            return True, ReasoningBreakdown(
                has_premise_support=True,
                has_logical_flow=True,
                avoids_speculation=True,
                has_conclusion_link=True,
                final_score=1.0,
            )

        # Extract context text
        context_text = " ".join(hit.text for hit in hits[:4])

        # Check premise support
        premise_support = self._check_premise_support(answer, context_text, embed_fn)

        # Check logical flow
        logical_flow = self._check_logical_flow(answer)

        # Check for speculation
        avoids_speculation = self._check_avoids_speculation(answer)

        # Check conclusion link
        conclusion_link = self._check_conclusion_link(answer, context_text)

        # Compute final score
        components = [premise_support, logical_flow, avoids_speculation, conclusion_link]
        final_score = sum(components) / len(components)

        is_valid = final_score >= self.premise_threshold

        if logger.isEnabledFor(logging.DEBUG):
            logger.debug(
                "Reasoning check: premise=%.2f flow=%.2f no_spec=%.2f conclusion=%.2f final=%.2f valid=%s",
                premise_support, logical_flow, avoids_speculation, conclusion_link,
                final_score, is_valid
            )

        return is_valid, ReasoningBreakdown(
            has_premise_support=premise_support >= 0.5,
            has_logical_flow=logical_flow >= 0.5,
            avoids_speculation=avoids_speculation >= 0.5,
            has_conclusion_link=conclusion_link >= 0.5,
            final_score=final_score,
        )

    def _check_premise_support(
        self,
        answer: str,
        context: str,
        embed_fn: Callable[[list[str]], list] | None = None,
    ) -> float:
        """Check if answer premises are supported by context."""
        if not embed_fn:
            # Fallback to lexical overlap if no embedding function
            return self._lexical_premise_support(answer, context)

        # Use semantic similarity for premise support
        try:
            # Split answer into sentences
            answer_sentences = self._split_sentences(answer)
            if not answer_sentences:
                return 1.0

            # Get context sentences
            context_sentences = self._split_sentences(context)
            if not context_sentences:
                return 1.0

            # Embed all sentences
            all_texts = answer_sentences + context_sentences
            embs = embed_fn(all_texts)

            answer_embs = embs[:len(answer_sentences)]
            context_embs = embs[len(answer_sentences):]

            # Check if each answer sentence has support in context
            supported_count = 0
            for a_emb in answer_embs:
                similarities = [self._cosine(a_emb, c_emb) for c_emb in context_embs]
                if max(similarities) >= 0.5:  # Lower threshold for premise support
                    supported_count += 1

            return supported_count / len(answer_sentences) if answer_sentences else 1.0

        except Exception as e:
            logger.warning(f"Semantic premise support check failed: {e}, using lexical fallback")
            return self._lexical_premise_support(answer, context)

    def _lexical_premise_support(self, answer: str, context: str) -> float:
        """Fallback lexical overlap check for premise support."""
        answer_tokens = set(answer.lower().split())
        context_tokens = set(context.lower().split())

        if not answer_tokens:
            return 1.0

        # Check for significant overlap
        overlap = len(answer_tokens & context_tokens)
        overlap_ratio = overlap / len(answer_tokens)

        # Require at least 30% token overlap for premise support
        return min(overlap_ratio / 0.3, 1.0)

    def _check_logical_flow(self, answer: str) -> float:
        """Check if answer has logical connectors indicating reasoning flow."""
        answer_lower = answer.lower()

        # Count logical connectors
        connector_count = sum(1 for conn in self.logical_connectors if conn in answer_lower)

        # Answers with logical connectors get higher scores
        if connector_count >= 2:
            return 1.0
        elif connector_count == 1:
            return 0.7
        else:
            # Short answers without connectors are still acceptable
            if len(answer.split()) < 20:
                return 0.8
            return 0.5

    def _check_avoids_speculation(self, answer: str) -> float:
        """Check if answer avoids speculative language."""
        if not self.enable_speculation_check:
            return 1.0

        answer_lower = answer.lower()

        # Check for speculative patterns
        speculative_count = sum(1 for pattern in self.speculative_patterns if pattern.search(answer_lower))

        if speculative_count == 0:
            return 1.0
        elif speculative_count == 1:
            return 0.5
        else:
            return 0.0

    def _check_conclusion_link(self, answer: str, context: str) -> float:
        """Check if answer conclusion is linked to context."""
        # Extract key entities from answer
        answer_entities = self._extract_entities(answer)
        context_entities = self._extract_entities(context)

        if not answer_entities:
            return 1.0

        # Check if answer entities appear in context
        linked_entities = sum(1 for entity in answer_entities if entity in context_entities)

        if not answer_entities:
            return 1.0

        link_ratio = linked_entities / len(answer_entities)
        return min(link_ratio / 0.5, 1.0)  # Require 50% entity overlap

    def _split_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        parts = re.split(r"(?<=[.!?])\s+", text.strip())
        return [p.strip() for p in parts if len(p.strip()) > 0]

    def _cosine(self, a, b) -> float:
        """Compute cosine similarity between two vectors."""
        import numpy as np
        return float(np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8))

    def _extract_entities(self, text: str) -> set[str]:
        """Extract simple entities (capitalized words, numbers)."""
        # Extract capitalized words (potential entities)
        entities = set(re.findall(r"\b[A-Z][a-z]+\b", text))
        # Extract numbers
        numbers = set(re.findall(r"\b\d+\b", text))
        entities.update(numbers)
        return entities
