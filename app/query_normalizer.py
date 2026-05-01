"""
Query normalizer — Arabic-aware preprocessing for retrieval.
v1: normalization only, no translation.

Normalization rules:
  - Hamza variants on alef (إ أ آ) → bare alef (ا)
  - Alef maqsura (ى) → ya (ي)
  - Hamza on waw (ؤ) → waw (و)
  - Hamza on ya (ئ) → ya (ي)
  - Strip tashkeel/diacritics (harakat)
  - Collapse whitespace
"""

import logging
import re

logger = logging.getLogger(__name__)

_ARABIC_RE = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF]+")
_DIACRITICS_RE = re.compile(r"[\u064B-\u065F\u0670]")


def is_arabic(text: str) -> bool:
    """Return True if text contains Arabic characters."""
    return bool(_ARABIC_RE.search(text))


def normalize_arabic(text: str) -> str:
    """
    Normalize Arabic text by standardizing common character variants.
    Non-Arabic text is returned unchanged.

    Examples:
      إيكو → ايكو
      متى → متي
      مؤسسة → موسسة
      طائفة → طايفة
      مَنْ → من
    """
    if not is_arabic(text):
        return re.sub(r"\s+", " ", text).strip()

    text = re.sub(r"[إأآ]", "ا", text)
    text = text.replace("ى", "ي")
    text = text.replace("ؤ", "و")
    text = text.replace("ئ", "ي")
    text = _DIACRITICS_RE.sub("", text)
    text = re.sub(r"\s+", " ", text).strip()

    return text


def normalize_query_with_flag(query: str) -> tuple[str, bool]:
    """
    Normalize a query for retrieval.
    Returns (normalized_query, was_normalized).
    """
    if not is_arabic(query):
        return query.strip(), False

    normalized = normalize_arabic(query)
    if normalized != query:
        logger.debug("Query normalized: %r → %r", query, normalized)
    return normalized, normalized != query


def normalize_query(query: str) -> str:
    """
    Normalize a query for retrieval.
    Returns normalized_query string only (for backward compatibility with router.features).
    """
    normalized, _ = normalize_query_with_flag(query)
    return normalized
