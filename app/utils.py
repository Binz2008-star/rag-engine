from __future__ import annotations

import hashlib
import json
import uuid
from pathlib import Path
from typing import Iterable


def new_query_id() -> str:
    return str(uuid.uuid4())


def jsonl_load(path: Path) -> list[dict]:
    if not path.exists():
        return []

    rows: list[dict] = []
    with open(path, "r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def jsonl_append(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def stable_hash(items: Iterable[str]) -> str:
    digest = hashlib.md5()
    for item in items:
        digest.update(item.encode("utf-8", errors="ignore"))
    return digest.hexdigest()
