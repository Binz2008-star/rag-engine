"""Clean intent dataset by removing conflicts, duplicates, and fixing labels."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.normalize_arabic import normalize_arabic


def clean_dataset(input_path: str, output_path: str) -> None:
    """Clean intent dataset by removing conflicts and duplicates.
    
    Args:
        input_path: Path to input JSONL file
        output_path: Path to output JSON file
    """
    # Load data
    data = []
    with open(input_path, "r", encoding="utf-8") as f:
        for line in f:
            if line.strip():
                data.append(json.loads(line))
    
    print(f"Loaded {len(data)} examples")
    
    # Track seen normalized queries and their intents
    seen = {}
    clean = []
    conflicts = []
    duplicates = []
    
    for d in data:
        q_raw = d["query"]
        q_norm = normalize_arabic(q_raw)
        intent = d["intent"]
        
        # Skip overly short queries
        if len(q_norm.split()) < 2:
            print(f"SKIP (too short): {q_raw}")
            continue
        
        # Check for conflicts or duplicates
        if q_norm in seen:
            if seen[q_norm] != intent:
                conflicts.append((q_raw, intent, seen[q_norm]))
                print(f"CONFLICT: '{q_raw}' → {intent} vs {seen[q_norm]}")
                continue  # Drop conflicting sample
            else:
                duplicates.append(q_raw)
                print(f"DUP: {q_raw}")
                continue  # Skip duplicate
        else:
            seen[q_norm] = intent
        
        # Fix known bad labels
        if "ignore previous instructions" in q_raw.lower():
            print(f"FIX: '{q_raw}' → general (was {intent})")
            intent = "general"
        
        # Merge profile into general
        if intent == "profile":
            print(f"MERGE: '{q_raw}' → general (was profile)")
            intent = "general"
        
        clean.append({
            "text": q_raw,
            "label": intent
        })
    
    print(f"\nSummary:")
    print(f"  Conflicts dropped: {len(conflicts)}")
    print(f"  Duplicates dropped: {len(duplicates)}")
    print(f"  Final size: {len(clean)}")
    
    # Save cleaned data
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(clean, f, indent=2, ensure_ascii=False)
    
    print(f"Saved to {output_path}")


if __name__ == "__main__":
    clean_dataset(
        input_path="data/intent_dataset.jsonl",
        output_path="data/intent_dataset_clean.json"
    )
