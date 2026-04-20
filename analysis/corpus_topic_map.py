"""
Corpus topic map — deterministic coverage analysis for KnowledgeGap enrichment.

Responsibility:
    Given a query and intent, return up to N topic labels that are *expected*
    but *not covered* by the current corpus. This is a signal — NOT a gate
    input, NOT a decision path.

Design rules (from canonical baseline):
    * No LLM calls.
    * One-shot build(), then O(1) lookups on topic_index.
    * Read only: chunk.source, chunk.doc_type, chunk.text[:_SAMPLE_CHARS].
    * Returns up to _MAX_MISSING labels to avoid UI flood.
    * Never mutates the KnowledgeGap schema — it only populates existing fields.

Contract:
    CorpusTopicMap(indexes).missing_documents_for(query, intent) -> list[str]
"""
from __future__ import annotations

import re
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:
    from retrieval.faiss_index import FaissIndex

# ── Configuration ──────────────────────────────────────────────────────────

_SAMPLE_CHARS = 200
_MAX_MISSING = 3
_MIN_TOPIC_LEN = 4  # discard short inferred tokens like "the", "what"

# Topics expected to exist per intent. Matched against chunk metadata with
# substring/keyword logic. Keep tight and explicit — no fuzzy magic.
_DEFAULT_EXPECTED_TOPICS: dict[str, tuple[str, ...]] = {
    "eco": (
        "regulations",
        "compliance",
        "certifications",
        "services",
        "contact",
        "environmental_permits",
        "waste_management",
    ),
    "cv": (
        "experience",
        "education",
        "certifications",
        "skills",
        "role",
        "contact",
    ),
    "general": (),
}

# Keyword aliases — each topic matches if any of these appears in the
# chunk source, doc_type, or first _SAMPLE_CHARS of text.
_TOPIC_KEYWORDS: dict[str, tuple[str, ...]] = {
    "regulations":           ("regulation", "law", "decree", "statute", "bylaw"),
    "compliance":            ("compliance", "compliant", "audit", "inspection"),
    "certifications":        ("certificate", "certification", "certified", "iso", "accredit"),
    "services":              ("service", "offering", "provide", "solution"),
    "contact":               ("contact", "email", "phone", "address", "linkedin"),
    "environmental_permits": ("permit", "license", "environmental permit", "municipal"),
    "waste_management":      ("waste", "wastewater", "grease", "disposal", "recycl"),
    "experience":            ("experience", "worked", "employment", "role", "position"),
    "education":             ("education", "degree", "university", "bachelor", "master"),
    "skills":                ("skill", "proficient", "fluent", "technical"),
    "role":                  ("role", "tailored", "position", "title"),
}

# Stop words for the inference fallback. Deliberately small — English only.
_STOP_WORDS = frozenset({
    "a", "an", "the", "is", "are", "was", "were", "be", "been", "being",
    "and", "or", "but", "if", "then", "else", "when", "where", "why", "how",
    "what", "who", "which", "that", "this", "these", "those",
    "of", "in", "on", "at", "to", "for", "with", "from", "by", "about",
    "do", "does", "did", "have", "has", "had", "can", "could", "should",
    "will", "would", "may", "might", "must", "shall",
    "i", "you", "he", "she", "it", "we", "they", "me", "him", "her", "us",
    "my", "your", "his", "its", "our", "their",
    "any", "some", "all", "no", "not", "only", "own", "same", "so", "than",
    "too", "very", "just", "also",
})


def _tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z_][a-z0-9_]{2,}", text.lower())


# ── CorpusTopicMap ─────────────────────────────────────────────────────────

class CorpusTopicMap:
    """
    Deterministic corpus coverage analysis.

    Call build() once (or let __init__ do it). Then missing_documents_for()
    is O(len(expected_topics)) plus a small token scan for the fallback.
    """

    def __init__(
        self,
        indexes: dict[str, FaissIndex],
        expected_topics: dict[str, tuple[str, ...]] | None = None,
        topic_keywords: dict[str, tuple[str, ...]] | None = None,
    ) -> None:
        self.indexes = indexes
        self.expected_topics = expected_topics or _DEFAULT_EXPECTED_TOPICS
        self.topic_keywords = topic_keywords or _TOPIC_KEYWORDS
        # topic_index[intent][topic] = True/False  (covered)
        self.topic_index: dict[str, dict[str, bool]] = {}
        # Flat set of all covered topics across the corpus (for fallback lookup).
        self._all_covered_topics: set[str] = set()
        self.build()

    # ── build ──────────────────────────────────────────────────────────────

    def build(self) -> None:
        """Scan each index once; mark every expected topic as covered or not."""
        self.topic_index = {}
        self._all_covered_topics = set()

        for intent, index in self.indexes.items():
            chunks = getattr(index, "chunks", []) or []
            haystack = self._build_haystack(chunks)
            coverage: dict[str, bool] = {}

            topics_to_check = self._topics_for_intent(intent)
            for topic in topics_to_check:
                covered = self._topic_exists_in_haystack(topic, haystack)
                coverage[topic] = covered
                if covered:
                    self._all_covered_topics.add(topic)

            self.topic_index[intent] = coverage

    def _build_haystack(self, chunks: Iterable) -> str:
        """Concatenate source, doc_type, and text samples into one lowercase string."""
        parts: list[str] = []
        for chunk in chunks:
            source = getattr(chunk, "source", "") or ""
            doc_type = getattr(chunk, "doc_type", "") or ""
            text = getattr(chunk, "text", "") or ""
            parts.append(source.lower())
            parts.append(doc_type.lower())
            parts.append(text[:_SAMPLE_CHARS].lower())
        return "\n".join(parts)

    def _topic_exists_in_haystack(self, topic: str, haystack: str) -> bool:
        for keyword in self.topic_keywords.get(topic, (topic,)):
            if keyword.lower() in haystack:
                return True
        return False

    def _topics_for_intent(self, intent: str) -> tuple[str, ...]:
        return self.expected_topics.get(intent, ())

    # ── Public API ─────────────────────────────────────────────────────────

    def missing_documents_for(
        self,
        query: str,
        intent: str | None = None,
    ) -> list[str]:
        """
        Return up to _MAX_MISSING topic labels signalling corpus gaps.

        Resolution order:
            1. If the intent has a configured expected topic set, report only
               the topics from that set that are absent from the corpus. A
               fully covered intent returns [].
            2. Otherwise (intent missing / None / empty expected set), fall
               back to tokens extracted from the query that are not already
               covered anywhere in the corpus.

        Safe for concurrent use after build() has run.
        """
        expected = self._topics_for_intent(intent) if intent else ()
        if expected:
            return self._missing_for_intent(intent)[:_MAX_MISSING]

        inferred = self._infer_from_query(query)
        return [topic for topic in inferred if topic not in self._all_covered_topics][
            :_MAX_MISSING
        ]

    def topic_exists(self, topic: str, intent: str | None = None) -> bool:
        """Public O(1) check for a single topic in a given intent (or globally)."""
        if intent is None:
            return topic in self._all_covered_topics
        return self.topic_index.get(intent, {}).get(topic, False)

    # ── Internal helpers ───────────────────────────────────────────────────

    def _missing_for_intent(self, intent: str | None) -> list[str]:
        if not intent:
            return []
        coverage = self.topic_index.get(intent, {})
        if not coverage:
            return []
        return [topic for topic, covered in coverage.items() if not covered]

    def _infer_from_query(self, query: str) -> list[str]:
        """
        Extract candidate topics from the query when no expected ones apply.
        Strict: no LLM, no stemming, deterministic.
        """
        tokens = _tokenize(query or "")
        seen: set[str] = set()
        result: list[str] = []
        for token in tokens:
            if len(token) < _MIN_TOPIC_LEN:
                continue
            if token in _STOP_WORDS:
                continue
            if token in seen:
                continue
            seen.add(token)
            result.append(token)
        return result
