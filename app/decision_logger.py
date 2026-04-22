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

    def log_intent(self, request_id: str, query: str, intent: str, method: str = "v1_keyword", confidence: float = 1.0) -> None:
        """Log intent classification decision.

        Args:
            request_id: Unique identifier for this request.
            query: The user query.
            intent: Detected intent (cv, eco, general, profile).
            method: Method used for detection (e.g., "v1_keyword").
            confidence: Confidence score (0.0-1.0). Default 1.0 for rule-based.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "schema_version": 1,
            "type": "intent",
            "query": query,
            "intent": intent,
            "confidence": confidence,
            "method": method,
        }
        self._append(entry)

    def log_retrieved(self, request_id: str, query: str, retrieved: list[dict]) -> None:
        """Log retrieved chunks BEFORE grouping.

        Args:
            request_id: Unique identifier for this request.
            query: The user query.
            retrieved: List of retrieved chunks with source, score, rank.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "schema_version": 1,
            "type": "retrieved",
            "query": query,
            "retrieved": retrieved,
        }
        self._append(entry)

    def log_grouped_order(self, request_id: str, query: str, grouped_order: list[str]) -> None:
        """Log document order AFTER grouping/priority.

        Args:
            request_id: Unique identifier for this request.
            query: The user query.
            grouped_order: List of document names in priority order.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "schema_version": 1,
            "type": "grouped_order",
            "query": query,
            "grouped_order": grouped_order,
        }
        self._append(entry)

    def log_final_chunks(self, request_id: str, query: str, final_chunks: list[dict]) -> None:
        """Log final selected chunks.

        Args:
            request_id: Unique identifier for this request.
            query: The user query.
            final_chunks: List of final chunks with chunk_id, source, score.
        """
        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "schema_version": 1,
            "type": "final_chunks",
            "query": query,
            "final_chunks": final_chunks,
        }
        self._append(entry)

    def log_shadow_comparison(
        self,
        request_id: str,
        query: str,
        primary_sources: list[str],
        advanced_sources: list[str] | None,
        primary_intent: str,
        advanced_intent: str | None,
        shadow_metadata: dict | None,
    ) -> None:
        """Log shadow mode comparison between primary and advanced retrieval.

        Args:
            request_id: Unique identifier for this request.
            query: The user query.
            primary_sources: List of sources from primary retrieval.
            advanced_sources: List of sources from advanced retrieval (if available).
            primary_intent: Intent from primary classification.
            advanced_intent: Intent from advanced classification (if available).
            shadow_metadata: Additional metadata from shadow retrieval execution.
        """
        # Calculate overlap
        primary_set = set(primary_sources)
        advanced_set = set(advanced_sources) if advanced_sources else set()
        overlap = list(primary_set & advanced_set)
        primary_only = list(primary_set - advanced_set)
        advanced_only = list(advanced_set - primary_set)

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id,
            "schema_version": 1,
            "type": "shadow_comparison",
            "query": query,
            "primary_sources": primary_sources,
            "advanced_sources": advanced_sources,
            "overlap": overlap,
            "primary_only": primary_only,
            "advanced_only": advanced_only,
            "primary_intent": primary_intent,
            "advanced_intent": advanced_intent,
            "intent_match": primary_intent == advanced_intent if advanced_intent else None,
            "shadow_metadata": shadow_metadata,
        }
        self._append(entry)

    def _append(self, entry: dict[str, Any]) -> None:
        """Append entry to JSONL log file."""
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        except Exception as e:
            logger.warning("Failed to write decision log: %s", e)
