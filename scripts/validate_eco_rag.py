#!/usr/bin/env python3
"""
Validate models/eco_rag_ready.jsonl before indexing.
"""

import json
from pathlib import Path
from typing import List, Dict, Set

INPUT_FILE = Path("models/eco_rag_ready.jsonl")

# Load all rows
rows = []
with open(INPUT_FILE, "r", encoding="utf-8") as f:
    for line in f:
        if line.strip():
            rows.append(json.loads(line))

print("=" * 60)
print("ECO RAG-Ready Dataset Validation")
print("=" * 60)
print(f"\nTotal rows loaded: {len(rows)}")

# 1. Validate schema fields
print("\n--- Schema Validation ---")
required_fields = ["id", "type", "intent", "entity", "text", "keywords", "source", "confidence"]
schema_errors = []
for i, row in enumerate(rows):
    for field in required_fields:
        if field not in row:
            schema_errors.append(f"Row {i}: Missing field '{field}'")

if schema_errors:
    print(f"Schema errors found: {len(schema_errors)}")
    for error in schema_errors:
        print(f"  - {error}")
else:
    print("✓ All rows have required schema fields")

# 2. Check for duplicate IDs
print("\n--- Duplicate ID Check ---")
ids = [row["id"] for row in rows]
id_counts = {}
for id in ids:
    id_counts[id] = id_counts.get(id, 0) + 1

duplicates = {id: count for id, count in id_counts.items() if count > 1}
if duplicates:
    print(f"Duplicate IDs found: {len(duplicates)}")
    for id, count in duplicates.items():
        print(f"  - {id}: {count} occurrences")
else:
    print("✓ No duplicate IDs")

# 3. Check for multi-claim rows
print("\n--- Multi-Claim Row Check ---")
multi_claim_patterns = [
    " and ", " or ", " plus ", " as well as ", " along with ",
    " including ", " such as "
]
multi_claim_rows = []
for i, row in enumerate(rows):
    text = row["text"].lower()
    # Check for conjunctions that might indicate multiple claims
    for pattern in multi_claim_patterns:
        if pattern in text:
            # Need to verify if it's actually multi-claim or single claim with list
            # Simple heuristic: if pattern appears and sentence structure suggests multiple facts
            words = text.split()
            if len(words) > 15:  # Longer sentences more likely to be multi-claim
                multi_claim_rows.append((row["id"], row["text"]))
                break

if multi_claim_rows:
    print(f"Potential multi-claim rows: {len(multi_claim_rows)}")
    for id, text in multi_claim_rows:
        print(f"  - {id}: {text[:80]}...")
else:
    print("✓ No obvious multi-claim rows")

# 4. Check for CTA/persuasion leakage
print("\n--- CTA/Persuasion Check ---")
cta_phrases = ["call", "contact us", "share", "send", "reach out", "get in touch", "choose", "select"]
persuasion_phrases = ["best", "top quality", "excellent", "premium", "outstanding", "superior"]
cta_rows = []
for i, row in enumerate(rows):
    text = row["text"].lower()
    for phrase in cta_phrases:
        if phrase in text:
            cta_rows.append((row["id"], row["text"], "CTA"))
            break
    for phrase in persuasion_phrases:
        if phrase in text:
            cta_rows.append((row["id"], row["text"], "persuasion"))
            break

if cta_rows:
    print(f"CTA/Persuasion leakage found: {len(cta_rows)}")
    for id, text, reason in cta_rows:
        print(f"  - {id} ({reason}): {text[:80]}...")
else:
    print("✓ No CTA or persuasion leakage")

# 5. Check for missing keywords
print("\n--- Missing Keywords Check ---")
missing_keyword_rows = []
for i, row in enumerate(rows):
    if not row["keywords"] or len(row["keywords"]) == 0:
        missing_keyword_rows.append(row["id"])

if missing_keyword_rows:
    print(f"Rows with missing keywords: {len(missing_keyword_rows)}")
    for id in missing_keyword_rows:
        print(f"  - {id}")
else:
    print("✓ All rows have keywords")

# 6. Check for unsupported claims
print("\n--- Unsupported Claims Check ---")
unsupported_patterns = ["80+", "500+", "best", "top", "#1", "leading", "premier"]
unsupported_rows = []
for i, row in enumerate(rows):
    text = row["text"].lower()
    for pattern in unsupported_patterns:
        if pattern in text:
            unsupported_rows.append((row["id"], row["text"]))
            break

if unsupported_rows:
    print(f"Potential unsupported claims: {len(unsupported_rows)}")
    for id, text in unsupported_rows:
        print(f"  - {id}: {text}")
else:
    print("✓ No obvious unsupported claims")

# 7. Critical correction checks
print("\n--- Critical Correction Checks ---")

# Check phone/WhatsApp multi-claim
phone_whatsapp_row = None
for row in rows:
    if "phone" in row["text"].lower() and "whatsapp" in row["text"].lower():
        phone_whatsapp_row = row
        break

if phone_whatsapp_row:
    print(f"⚠ Phone/WhatsApp multi-claim found: {phone_whatsapp_row['id']}")
    print(f"  Text: {phone_whatsapp_row['text']}")
else:
    print("✓ No phone/WhatsApp multi-claim")

# Check for "most popular" marketing claim
most_popular_rows = []
for row in rows:
    if "most popular" in row["text"].lower():
        most_popular_rows.append((row["id"], row["text"]))

if most_popular_rows:
    print(f"⚠ 'Most popular' marketing claims: {len(most_popular_rows)}")
    for id, text in most_popular_rows:
        print(f"  - {id}: {text}")
else:
    print("✓ No 'most popular' marketing claims")

# 8. Run retrieval probe queries
print("\n--- Retrieval Probe Queries ---")

probe_queries = [
    "Who founded ECO?",
    "Who is the founder of ECO?",
    "When was ECO founded?",
    "What is ECO phone number?",
    "How much is grease trap Size B?",
    "What does AMC include?",
    "Do you work in Dubai?",
    "What happens if grease trap is not cleaned?",
    "Do you recycle used cooking oil?"
]

def simple_keyword_match(query: str, row: Dict) -> bool:
    """Simple keyword matching for probe queries."""
    query_lower = query.lower()
    text_lower = row["text"].lower()
    keywords_lower = [k.lower() for k in row["keywords"]]

    # Extract key terms from query
    if "founder" in query_lower and "who" in query_lower:
        return "founder" in text_lower and "robin" in text_lower
    elif "founded" in query_lower and "who" in query_lower:
        return "robin" in text_lower or "edwan" in text_lower or "founder" in text_lower
    elif "founded" in query_lower and "when" in query_lower:
        return "2016" in text_lower
    elif "phone" in query_lower:
        return "phone" in text_lower
    elif "grease trap" in query_lower and "size b" in query_lower:
        return "size b" in text_lower and "grease trap" in text_lower
    elif "amc" in query_lower and "include" in query_lower:
        return "amc" in text_lower
    elif "dubai" in query_lower:
        return "dubai" in text_lower
    elif "grease trap" in query_lower and "not cleaned" in query_lower:
        # This likely won't match - checking for absence
        return False
    elif "cooking oil" in query_lower and "recycle" in query_lower:
        return "cooking oil" in text_lower or "uco" in text_lower

    return False

print("\nQuery -> Row ID Mapping:")
for query in probe_queries:
    matches = []
    for row in rows:
        if simple_keyword_match(query, row):
            matches.append(row["id"])

    if matches:
        print(f"  '{query}' -> {matches}")
    else:
        print(f"  '{query}' -> NO MATCH")

print("\n" + "=" * 60)
print("Validation Complete")
print("=" * 60)
