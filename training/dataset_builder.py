from __future__ import annotations

from collections import Counter

from training.validators import is_valid_sample


def build_dataset_from_events(events: list[dict]) -> list[dict]:
    dataset: list[dict] = []
    seen: set[tuple[str, str, str]] = set()

    for event in events:
        if event.get("event_type") not in {"generation_result", "failure"}:
            continue

        query = event.get("normalized_query") or event.get("query")
        intent = event.get("intent")
        failure_type = event.get("failure_type")

        if not query or not intent or intent == "uncertain":
            continue

        key = (query, intent, failure_type or "ok")
        if key in seen:
            continue
        seen.add(key)

        if not is_valid_sample(query, intent):
            continue

        row = {
            "query": query,
            "label": intent,
            "label_source": "production" if failure_type is None else "failure_fix",
        }
        if failure_type:
            row["failure_type"] = failure_type
        dataset.append(row)

    return dataset


def summarize_labels(dataset: list[dict]) -> dict[str, int]:
    counts = Counter(row["label"] for row in dataset)
    return dict(counts)
