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
    # Unify ECO variant (already lowercased and normalized)
    text = text.replace("ايكو", "eco")
    return text.strip()


def extract_hints(query: str) -> tuple[bool, bool]:
    q = normalize_query(query)

    eco_terms = {
        "eco", "company", "environment", "environmental", "municipality",
        "waste", "wastewater", "grease", "compliance", "audit",
    }
    cv_terms = {
        "cv", "resume", "tailored", "role", "experience",
        "skills", "certificates", "deliveroo", "job", "roben", "roben's",
        "employment", "employment history", "work history", "worked for",
        "companies worked", "companies has", "companies has robin worked",
        "previous roles", "career history", "applying for",
        "position does", "position does robin want", "job is the cv for",
        "خبرة", "روبن", "خبر", "سيرة", "ذاتية",
    }
    general_terms = {
        "mars", "planet", "galaxy", "jupiter", "gdp", "economy",
    }

    if any(term in q for term in general_terms):
        return False, False

    return (
        any(term in q for term in eco_terms),
        any(term in q for term in cv_terms),
    )
