from __future__ import annotations

from router.features import normalize_query

GENERAL_BANNED = {
    "cv",
    "resume",
    "job",
    "career",
    "employee",
    "work",
    "skills",
    "experience",
    "manager",
    "team",
    "eco",
    "robin",
}


def is_valid_sample(query: str, label: str) -> bool:
    normalized = normalize_query(query)
    if not normalized or len(normalized) < 3:
        return False
    if label not in {"cv", "eco", "general"}:
        return False
    if label == "general":
        if len(normalized.split()) < 3:
            return False
        if any(term in normalized for term in GENERAL_BANNED):
            return False
    return True
