"""Simple SQLite-backed leads store.

Leads are captured from chat interactions (queries routed through the
RAG pipeline). Each lead records the user question, the detected intent,
a temperature classification (hot / warm / cold), and a timestamp.

The store is intentionally minimal — no ORM, no migrations — so it can
run alongside the existing ``events.db`` without adding framework weight.
"""

from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.config import LOG_DIR

_DB_PATH = LOG_DIR / "leads.db"


class LeadsStore:
    """Thread-safe SQLite lead store (one connection per instance)."""

    def __init__(self, db_path: Optional[Path] = None) -> None:
        self._db_path = db_path or _DB_PATH
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_schema()

    def _init_schema(self) -> None:
        self._conn.executescript(
            """
            CREATE TABLE IF NOT EXISTS leads (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                query      TEXT    NOT NULL,
                intent     TEXT    NOT NULL DEFAULT 'general',
                temperature TEXT   NOT NULL DEFAULT 'cold',
                source     TEXT    NOT NULL DEFAULT 'chat',
                session_id TEXT,
                user_id    TEXT,
                metadata   TEXT,
                created_at REAL   NOT NULL
            );
            CREATE INDEX IF NOT EXISTS idx_leads_temp ON leads(temperature);
            CREATE INDEX IF NOT EXISTS idx_leads_ts   ON leads(created_at);
            """
        )

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def capture(
        self,
        query: str,
        intent: str = "general",
        temperature: str = "cold",
        source: str = "chat",
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> int:
        """Insert a new lead and return its row id."""
        cur = self._conn.execute(
            """INSERT INTO leads
               (query, intent, temperature, source, session_id, user_id, metadata, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                query,
                intent,
                temperature,
                source,
                session_id,
                user_id,
                json.dumps(metadata) if metadata else None,
                time.time(),
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    # ------------------------------------------------------------------
    # Read helpers
    # ------------------------------------------------------------------

    def _rows_to_dicts(self, rows: list[sqlite3.Row]) -> List[Dict[str, Any]]:
        result: List[Dict[str, Any]] = []
        for r in rows:
            d = dict(r)
            if d.get("metadata"):
                try:
                    d["metadata"] = json.loads(d["metadata"])
                except (json.JSONDecodeError, TypeError):
                    pass
            result.append(d)
        return result

    def list_all(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM leads ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return self._rows_to_dicts(rows)

    def list_by_temperature(
        self, temperature: str, limit: int = 100
    ) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM leads WHERE temperature = ? ORDER BY created_at DESC LIMIT ?",
            (temperature, limit),
        ).fetchall()
        return self._rows_to_dicts(rows)

    def counts_by_temperature(self) -> Dict[str, int]:
        rows = self._conn.execute(
            "SELECT temperature, COUNT(*) as cnt FROM leads GROUP BY temperature"
        ).fetchall()
        counts = {r["temperature"]: r["cnt"] for r in rows}
        for t in ("hot", "warm", "cold"):
            counts.setdefault(t, 0)
        return counts

    def total_count(self) -> int:
        row = self._conn.execute("SELECT COUNT(*) as cnt FROM leads").fetchone()
        return row["cnt"] if row else 0


# Module-level singleton
_store: Optional[LeadsStore] = None


def get_leads_store() -> LeadsStore:
    global _store
    if _store is None:
        _store = LeadsStore()
    return _store
