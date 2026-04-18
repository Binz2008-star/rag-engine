"""DecisionLogger - logs RAG pipeline decisions for observability."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any
from datetime import datetime

logger = logging.getLogger(__name__)


class DecisionLogger:
    """Logs RAG pipeline decisions to JSONL file for observability."""

    def __init__(self, log_path: str | Path = "logs/decisions.jsonl") -> None:
        """Initialize the decision logger.

        Args:
            log_path: Path to the JSONL log file (append-only).
        """
        self.log_path = Path(log_path)
        self.log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_intent(self, query: str, intent: str, method: str = "v1_keyword", confidence: float = 1.0) -> None:
        """Log intent classification decision.

        Args:
            query: The user query.
            intent: Detected intent (cv, eco, general, profile).
            method: Method used for detection (e.g., "v1_keyword").
            confidence: Confidence score (0.0-1.0). Default 1.0 for rule-based.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "intent",
            "query": query,
            "intent": intent,
            "confidence": confidence,
            "method": method,
        }
        self._append(entry)

    def log_retrieved(self, query: str, retrieved: list[dict]) -> None:
        """Log retrieved chunks BEFORE grouping.

        Args:
            query: The user query.
            retrieved: List of retrieved chunks with source, score, rank.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "retrieved",
            "query": query,
            "retrieved": retrieved,
        }
        self._append(entry)

    def log_grouped_order(self, query: str, grouped_order: list[str]) -> None:
        """Log document order AFTER grouping/priority.

        Args:
            query: The user query.
            grouped_order: List of document names in priority order.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "grouped_order",
            "query": query,
            "grouped_order": grouped_order,
        }
        self._append(entry)

    def log_final_chunks(self, query: str, final_chunks: list[dict]) -> None:
        """Log final selected chunks.

        Args:
            query: The user query.
            final_chunks: List of final chunks with chunk_id, source, score.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "type": "final_chunks",
            "query": query,
            "final_chunks": final_chunks,
        }
        self._append(entry)

    def _append(self, entry: dict[str, Any]) -> None:
        """Append entry to JSONL log file."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to write decision log: %s", e)
