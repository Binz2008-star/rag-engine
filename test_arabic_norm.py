"""Test Arabic normalization function."""

from app.query_normalizer import normalize_arabic, is_arabic

# Test cases for character-level normalization only
test_cases = [
    ("من هو روبن إدوان؟", "من هو روبن ادوان؟"),
    ("ما هي خدمات إيكو؟", "ما هي خدمات ايكو؟"),
    ("أين يقع إيكو؟", "اين يقع ايكو؟"),
    ("ما هو تعليم روبن؟", "ما هو تعليم روبن؟"),
    ("Hello world", "Hello world"),  # Non-Arabic should remain unchanged
]

print("Testing Arabic character-level normalization:")
print("=" * 60)

for original, expected in test_cases:
    normalized = normalize_arabic(original)
    status = "✓" if normalized == expected else "✗"
    print(f"{status} Original: {original}")
    print(f"  Expected: {expected}")
    print(f"  Got:      {normalized}")
    print(f"  Is Arabic: {is_arabic(original)}")
    print()

print("\nNote: Full pipeline (normalize + translate) is tested in test_arabic.py")
