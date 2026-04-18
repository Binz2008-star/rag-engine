#!/usr/bin/env python3
"""Build intent classification dataset from eval queries."""

import json
from pathlib import Path
from typing import Dict, List, Tuple

# Add parent to path to import app modules
import sys
sys.path.append(str(Path(__file__).parent.parent))

from app.query_normalizer import normalize_query
from app.retriever import Retriever
from app.embeddings import EmbeddingClient


def load_eval_queries() -> List[Dict]:
    """Load queries from eval file."""
    eval_path = Path(__file__).parent.parent / "tests" / "eval_queries.json"
    with open(eval_path, encoding="utf-8") as f:
        return json.load(f)


def extract_queries_with_labels(eval_data: List[Dict]) -> List[Tuple[str, str]]:
    """Extract queries and their intent labels using rule-based detection."""
    retriever = Retriever(EmbeddingClient())
    dataset = []

    for item in eval_data:
        query = item["question"]

        # Get intent using rule-based method
        intent = retriever._detect_query_type(query)

        # Add original query
        dataset.append((query, intent))

        # If Arabic, also add normalized version
        if retriever._contains_arabic(query):
            normalized, _ = normalize_query(query)
            if normalized != query:
                norm_intent = retriever._detect_query_type(normalized)
                dataset.append((normalized, norm_intent))

    return dataset


def save_dataset(dataset: List[Tuple[str, str]], output_path: Path) -> None:
    """Save dataset as JSONL."""
    # Convert to list of dicts
    dataset_dicts = [
        {"query": query, "intent": intent}
        for query, intent in dataset
    ]

    # Remove duplicates while preserving order
    seen = set()
    unique_dataset = []
    for item in dataset_dicts:
        key = (item["query"], item["intent"])
        if key not in seen:
            seen.add(key)
            unique_dataset.append(item)

    # Save as JSONL
    with open(output_path, "w", encoding="utf-8") as f:
        for item in unique_dataset:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"Dataset saved to {output_path}")
    print(f"Total examples: {len(unique_dataset)}")

    # Show distribution
    intent_counts = {}
    for item in unique_dataset:
        intent_counts[item["intent"]] = intent_counts.get(item["intent"], 0) + 1

    print("\nIntent distribution:")
    for intent, count in sorted(intent_counts.items()):
        print(f"  {intent}: {count}")


def main():
    """Build intent dataset from eval queries."""
    print("Building intent dataset...")

    # Load eval queries
    eval_data = load_eval_queries()
    print(f"Loaded {len(eval_data)} eval queries")

    # Extract queries with labels
    dataset = extract_queries_with_labels(eval_data)

    # Save dataset
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(exist_ok=True)
    output_path = output_dir / "intent_dataset.jsonl"

    save_dataset(dataset, output_path)

    # Show some examples
    print("\nSample examples:")
    with open(output_path, encoding="utf-8") as f:
        for i, line in enumerate(f):
            if i >= 5:
                break
            item = json.loads(line)
            print(f"  Query: {item['query'][:50]}...")
            print(f"  Intent: {item['intent']}")
            print()


if __name__ == "__main__":
    main()
