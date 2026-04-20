from __future__ import annotations

import json

from app.config import ACTIVE_MODEL_PATH, MODEL_REGISTRY_PATH
from app.utils import jsonl_append


def register_model(
    version: str,
    path: str,
    metrics: dict,
    dataset_hash: str,
    status: str = "staging",
    threshold: float = 0.60,
) -> None:
    row = {
        "version": version,
        "path": path,
        "status": status,
        "dataset_hash": dataset_hash,
        "metrics": metrics,
        "threshold": threshold,
    }
    jsonl_append(MODEL_REGISTRY_PATH, row)


def activate_model(version: str) -> None:
    entries: list[dict] = []
    if MODEL_REGISTRY_PATH.exists():
        with open(MODEL_REGISTRY_PATH, "r", encoding="utf-8") as handle:
            for line in handle:
                entries.append(json.loads(line))

    target = None
    for entry in entries:
        if entry["version"] == version:
            entry["status"] = "active"
            target = entry
        elif entry.get("status") == "active":
            entry["status"] = "archived"

    if target is None:
        raise ValueError(f"Unknown model version: {version}")

    with open(MODEL_REGISTRY_PATH, "w", encoding="utf-8") as handle:
        for entry in entries:
            handle.write(json.dumps(entry, ensure_ascii=False) + "\n")

    ACTIVE_MODEL_PATH.write_text(
        json.dumps(target, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
