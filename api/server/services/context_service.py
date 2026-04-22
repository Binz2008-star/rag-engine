"""In-memory session context for conversation history.

Stores recent interactions per session to enable context-aware responses.
Limited to 20 interactions per session to bound memory usage.
Thread-safe using RLock.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from threading import RLock
from time import time
from typing import DefaultDict


@dataclass(slots=True)
class InteractionRecord:
    timestamp: float
    session_id: str
    user_id: str | None
    question: str
    answer: str
    grounded: bool
    failure_type: str | None
    sources_count: int
    latency_ms: int


class ContextService:
    def __init__(self, max_per_session: int = 20) -> None:
        if max_per_session <= 0:
            raise ValueError("max_per_session must be greater than zero")

        self._max_per_session = max_per_session
        self._sessions: DefaultDict[str, list[InteractionRecord]] = defaultdict(list)
        self._lock = RLock()

    def add_interaction(self, record: InteractionRecord) -> None:
        if not record.session_id.strip():
            raise ValueError("session_id must not be empty")

        with self._lock:
            bucket = self._sessions[record.session_id]
            bucket.append(record)
            if len(bucket) > self._max_per_session:
                del bucket[:-self._max_per_session]

    def get_recent(self, session_id: str, limit: int = 6) -> list[InteractionRecord]:
        if not session_id.strip():
            return []

        if limit <= 0:
            return []

        with self._lock:
            bucket = self._sessions.get(session_id, [])
            return list(bucket[-limit:])

    def format_for_model(self, session_id: str, limit: int = 6) -> str:
        records = self.get_recent(session_id=session_id, limit=limit)
        if not records:
            return ""

        lines: list[str] = []
        for idx, item in enumerate(records, start=1):
            lines.append(f"[Turn {idx}]")
            lines.append(f"User: {item.question}")
            lines.append(f"Assistant: {item.answer}")
            lines.append(
                "Meta: "
                f"grounded={str(item.grounded).lower()}, "
                f"failure_type={item.failure_type or 'null'}, "
                f"sources={item.sources_count}, "
                f"latency_ms={item.latency_ms}"
            )

        return "\n".join(lines)

    def summarize_session(self, session_id: str) -> dict[str, object]:
        records = self.get_recent(session_id=session_id, limit=self._max_per_session)

        total = len(records)
        grounded_count = sum(1 for item in records if item.grounded)
        refusal_count = sum(1 for item in records if item.failure_type is not None)
        avg_latency_ms = (
            int(sum(item.latency_ms for item in records) / total) if total > 0 else 0
        )

        return {
            "session_id": session_id,
            "total_interactions": total,
            "grounded_count": grounded_count,
            "refusal_count": refusal_count,
            "avg_latency_ms": avg_latency_ms,
            "generated_at": time(),
        }
