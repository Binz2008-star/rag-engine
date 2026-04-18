from __future__ import annotations

import re

_ARABIC_MAP = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ى": "ي",
        "ؤ": "و",
        "ئ": "ي",
        "ة": "ه",
    }
)


def is_arabic(text: str) -> bool:
    return any("\u0600" <= char <= "\u06FF" for char in text)


def normalize_arabic(text: str) -> str:
    return text.translate(_ARABIC_MAP)


def normalize_query(text: str) -> str:
    text = (text or "").strip()
    if is_arabic(text):
        text = normalize_arabic(text)
    text = text.lower()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def extract_hints(query: str) -> tuple[bool, bool]:
    q = normalize_query(query)
    eco_keywords = {
        "eco",
        "environmental",
        "municipality",
        "wastewater",
        "grease",
        "company",
        "technology",
    }
    cv_keywords = {
        "cv",
        "resume",
        "experience",
        "education",
        "skills",
        "career",
        "certificate",
        "certifications",
        "deliveroo",
    }
    eco_hint = any(term in q for term in eco_keywords)
    cv_hint = any(term in q for term in cv_keywords)
    return eco_hint, cv_hint
