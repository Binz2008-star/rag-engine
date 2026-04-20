"""Shared text-predicate helpers used during refusal / answer validation.

Single source of truth. Both the CI runner (``eval_runner.py``) and the
training-path metrics module (``evaluation/metrics.py``) import from
here so they agree on:
  * what counts as a valid refusal,
  * whether an answer contains Arabic characters,
  * whether an answer contains numeric digits.

Duplicating any of these predicates silently produces inconsistent
metrics between workflows.
"""
from __future__ import annotations

from app.config import REFUSAL_MESSAGE

# Ordered from most specific to most generic. Matching is substring, case
# insensitive, and deliberately permissive: the LLM is instructed to emit
# ``REFUSAL_MESSAGE`` exactly, but real outputs drift ("I don't have
# enough information", "No data available", etc.). Accepting any of these
# counts as a refusal for metric purposes.
_REFUSAL_KEYWORDS: tuple[str, ...] = (
    "insufficient",
    "not enough",
    "no data",
    "no information",
    "not found",
    "i don't have",
    "cannot find",
    "no available data",
    "i don't know",
    "not available",
    "cannot provide",
    "unable to find",
    "no information available",
)


def is_insufficient_response(answer: str) -> bool:
    """Return True when the answer semantically matches a refusal.

    Uses keyword substring matching (lowercased). The canonical refusal
    message ``REFUSAL_MESSAGE`` always matches because "insufficient" is
    in the keyword list.
    """
    if not answer:
        return False
    lowered = answer.lower()
    return any(keyword in lowered for keyword in _REFUSAL_KEYWORDS)


def is_exact_refusal(answer: str) -> bool:
    """Return True only when the answer equals ``REFUSAL_MESSAGE`` exactly.

    Useful for the canonical refusal_accuracy metric where we want to
    measure how often the model followed the prompt verbatim (as opposed
    to emitting a semantically-equivalent paraphrase).
    """
    return str(answer or "").strip().lower() == REFUSAL_MESSAGE.lower()


def contains_arabic(text: str) -> bool:
    """Return True when ``text`` contains any character in the Arabic block.

    Used by the multilingual-output eval suite to detect language leakage
    in answers that are required to be English-only.
    """
    if not text:
        return False
    return any("\u0600" <= c <= "\u06FF" for c in text)


def contains_numbers(text: str) -> bool:
    """Return True when ``text`` contains any decimal digit.

    Used to flag hallucination risk on refusal responses: a valid
    refusal should not introduce numeric claims.
    """
    if not text:
        return False
    return any(c.isdigit() for c in text)
