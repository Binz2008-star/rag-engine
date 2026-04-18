"""Arabic text normalization for intent dataset cleaning."""

import re


def normalize_arabic(text: str) -> str:
    """Normalize Arabic text to handle hamza and other variants.

    Args:
        text: Input Arabic text

    Returns:
        Normalized text
    """
    text = text.strip().lower()

    # Normalize Hamza variants (إ أ آ ا → ا)
    text = re.sub(r"[إأآا]", "ا", text)

    # Normalize yaa/alif maqsura (ى ي → ي)
    text = re.sub(r"[ىي]", "ي", text)

    # Remove tatweel (ـ)
    text = re.sub(r"ـ", "", text)

    # Remove punctuation (Arabic + English)
    text = re.sub(r"[^\w\s]", "", text)

    return text


if __name__ == "__main__":
    # Test
    test_cases = [
        "ما هي شركة إيكو؟",
        "ما هي شركة ايكو؟",
        "أين تقع شركة إيكو؟",
        "اين تقع شركة ايكو؟",
    ]

    for case in test_cases:
        print(f"{case} → {normalize_arabic(case)}")
