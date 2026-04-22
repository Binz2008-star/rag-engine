"""Persistent logging of API interactions to JSONL.

Writes all requests to logs/api_interactions.jsonl for audit and analysis.
Logging failures must not break requests.
"""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class LoggedRequest:
    request_id: str
    timestamp: float
    route: str
    session_id: str | None
    user_id: str | None
    question: str
    answer: str
    grounded: bool
    failure_type: str | None
    latency_ms: int
    wall_ms: int
    intent: str
    sources_count: int


class InteractionLogService:
    def __init__(self, log_path: str | Path = "logs/api_interactions.jsonl") -> None:
        self._log_path = Path(log_path)
        self._log_path.parent.mkdir(parents=True, exist_ok=True)

    def log_request(self, item: LoggedRequest) -> None:
        try:
            with self._log_path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
        except Exception as exc:
            logger.warning("Failed to write interaction log: %s", exc)
