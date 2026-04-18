import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from scripts.text_normalization import normalize_query

ALLOWED_LABELS = {"eco", "cv", "general"}


def load_jsonl(path: str):
    with open(path, encoding="utf-8") as f:
        content = f.read()
        # Try JSONL first (line-by-line)
        try:
            for line in content.strip().split('\n'):
                if line.strip():
                    yield json.loads(line)
        except json.JSONDecodeError:
            # Fall back to JSON array
            for item in json.loads(content):
                yield item


def extract_row(item: dict, require_human: bool) -> dict | None:
    q = item.get("query") or item.get("text")
    label = item.get("label") or item.get("intent")

    if not q or not label:
        return None

    normalized = normalize_query(q)
    if not normalized:
        return None

    if label not in ALLOWED_LABELS:
        return None

    if require_human and item.get("label_source") != "human":
        return None

    return {
        "text": q,
        "label": label,
        "label_source": item.get("label_source", ""),
    }


def main():
    merged: dict[str, dict] = {}

    # Base data first (try both .json and .jsonl)
    base_path_jsonl = Path("data/intent_dataset_clean.jsonl")
    base_path_json = Path("data/intent_dataset_clean.json")
    base_path = base_path_jsonl if base_path_jsonl.exists() else base_path_json

    if base_path.exists():
        base_count = 0
        for item in load_jsonl(base_path):
            row = extract_row(item, require_human=False)
            if row is None:
                continue
            merged[normalize_query(row["text"])] = row
            base_count += 1
        print(f"Loaded base dataset: {base_count} valid samples")
    else:
        print(f"Base dataset not found, starting empty")

    # Human-reviewed data overrides base
    human_path = Path("data/intent_dataset_human.jsonl")
    if human_path.exists():
        human_count = 0
        for item in load_jsonl(human_path):
            row = extract_row(item, require_human=True)
            if row is None:
                continue
            merged[normalize_query(row["text"])] = row
            human_count += 1
        print(f"Loaded human-reviewed dataset: {human_count} valid samples (overrides base)")
    else:
        print(f"Human-reviewed dataset not found at {human_path}, no overrides")

    output_path = Path("data/train.jsonl")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        for row in merged.values():
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    print(f"Merged dataset: {len(merged)} samples → {output_path}")


if __name__ == "__main__":
    main()
