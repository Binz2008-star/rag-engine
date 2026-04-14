"""Query logger - logs queries, answers, sources, and timestamps."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path
from typing import Any, Dict

from app.config import BASE_DIR

logger = logging.getLogger(__name__)

LOGS_DIR = BASE_DIR / "logs"
QUERY_LOG_FILE = LOGS_DIR / "queries.jsonl"


def log_query(
    query: str,
    answer: str,
    sources: list[Dict[str, Any]],
    retrieval_time: float,
    generation_time: float,
) -> None:
    """Log a query with its response to the query log file."""
    try:
        LOGS_DIR.mkdir(exist_ok=True)

        is_refusal = answer.strip() == "Insufficient data."

        log_entry = {
            "query_id": str(uuid.uuid4()),
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "query": query,
            "answer": answer,
            "is_refusal": is_refusal,
            "source_files": [s["source"] for s in sources],
            "chunk_ids": [s["chunk_id"] for s in sources],
            "num_sources": len(sources),
            "retrieval_time_seconds": retrieval_time,
            "generation_time_seconds": generation_time,
            "total_time_seconds": retrieval_time + generation_time,
        }

        with open(QUERY_LOG_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

        logger.debug("Query logged to %s", QUERY_LOG_FILE)
    except Exception as e:
        logger.warning("Failed to log query: %s", e)
