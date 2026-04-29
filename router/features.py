from __future__ import annotations

import re

_ARABIC_MAP = str.maketrans({
    "أ": "ا",
    "إ": "ا",
    "آ": "ا",
    "ى": "ي",
    "ؤ": "و",
    "ئ": "ي",
    "ة": "ه",
})


def is_arabic(text: str) -> bool:
    return any(chr(0x0600) <= c <= chr(0x06FF) for c in text)


def normalize_arabic(text: str) -> str:
    return text.translate(_ARABIC_MAP)


def normalize_query(text: str) -> str:
    text = (text or "").strip()
    if is_arabic(text):
        text = normalize_arabic(text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    # Unify ECO variants
    text = text.replace("ايكو", "eco")
    text = text.replace("إيكو", "eco")
    return text.strip()


def extract_hints(query: str) -> tuple[bool, bool]:
    q = normalize_query(query)

    eco_terms = {
        "eco", "company", "environment", "environmental", "municipality",
        "waste", "wastewater", "grease", "compliance", "audit",
        "price", "pricing", "cost", "aed", "quote", "maintenance",
        "grease trap", "amc",
        "size a", "size b", "size c", "size d",
    }
    cv_terms = {
        "cv", "resume", "tailored", "role", "experience",
        "skills", "certificates", "deliveroo", "job", "roben", "roben's",
        # Arabic CV terms
        "خبرة", "روبن", "خبر", "سيرة", "ذاتية",
    }
    general_terms = {
        "mars", "planet", "galaxy", "jupiter", "gdp", "economy",
    }

    # General terms override eco/cv hints
    if any(term in q for term in general_terms):
        return False, False

    eco_hint = any(term in q for term in eco_terms)
    cv_hint = any(term in q for term in cv_terms)
    return eco_hint, cv_hint
