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
        self._migrate()

    def _migrate(self) -> None:
        """Add columns introduced after initial schema (idempotent)."""
        existing = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(leads)").fetchall()
        }
        migrations = [
            ("channel", "TEXT NOT NULL DEFAULT 'api'"),
            ("latency_ms", "INTEGER"),
            ("failure_type", "TEXT"),
            ("answer", "TEXT"),
            ("flagged", "INTEGER NOT NULL DEFAULT 0"),
        ]
        for col, typedef in migrations:
            if col not in existing:
                self._conn.execute(
                    f"ALTER TABLE leads ADD COLUMN {col} {typedef}"
                )
        self._conn.commit()

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
        channel: str = "api",
        latency_ms: Optional[int] = None,
        failure_type: Optional[str] = None,
        answer: Optional[str] = None,
    ) -> int:
        """Insert a new lead and return its row id."""
        cur = self._conn.execute(
            """INSERT INTO leads
               (query, intent, temperature, source, session_id, user_id,
                metadata, created_at, channel, latency_ms, failure_type, answer)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                query,
                intent,
                temperature,
                source,
                session_id,
                user_id,
                json.dumps(metadata) if metadata else None,
                time.time(),
                channel,
                latency_ms,
                failure_type,
                answer,
            ),
        )
        self._conn.commit()
        return cur.lastrowid  # type: ignore[return-value]

    def flag(self, lead_id: int, flagged: bool = True) -> bool:
        """Toggle the flagged state of a lead. Returns True if updated."""
        cur = self._conn.execute(
            "UPDATE leads SET flagged = ? WHERE id = ?",
            (1 if flagged else 0, lead_id),
        )
        self._conn.commit()
        return cur.rowcount > 0

    def get_by_id(self, lead_id: int) -> Optional[Dict[str, Any]]:
        row = self._conn.execute(
            "SELECT * FROM leads WHERE id = ?", (lead_id,)
        ).fetchone()
        if row is None:
            return None
        rows = self._rows_to_dicts([row])
        return rows[0] if rows else None

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

    def list_failures(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM leads WHERE failure_type IS NOT NULL "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
        ).fetchall()
        return self._rows_to_dicts(rows)

    def list_flagged(self, limit: int = 100) -> List[Dict[str, Any]]:
        rows = self._conn.execute(
            "SELECT * FROM leads WHERE flagged = 1 "
            "ORDER BY created_at DESC LIMIT ?",
            (limit,),
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

    def monitoring_stats(self) -> Dict[str, Any]:
        """Aggregate stats for the monitoring panel."""
        total = self.total_count()
        failure_row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM leads WHERE failure_type IS NOT NULL"
        ).fetchone()
        failures = failure_row["cnt"] if failure_row else 0
        flagged_row = self._conn.execute(
            "SELECT COUNT(*) as cnt FROM leads WHERE flagged = 1"
        ).fetchone()
        flagged = flagged_row["cnt"] if flagged_row else 0
        avg_row = self._conn.execute(
            "SELECT AVG(latency_ms) as avg_ms FROM leads WHERE latency_ms IS NOT NULL"
        ).fetchone()
        avg_latency = round(avg_row["avg_ms"]) if avg_row and avg_row["avg_ms"] else 0
        p95_row = self._conn.execute(
            "SELECT latency_ms FROM leads WHERE latency_ms IS NOT NULL "
            "ORDER BY latency_ms DESC LIMIT 1 OFFSET "
            "(SELECT CAST(COUNT(*) * 0.05 AS INTEGER) FROM leads WHERE latency_ms IS NOT NULL)"
        ).fetchone()
        p95_latency = p95_row["latency_ms"] if p95_row else 0

        channel_rows = self._conn.execute(
            "SELECT channel, COUNT(*) as cnt FROM leads GROUP BY channel"
        ).fetchall()
        by_channel = {r["channel"]: r["cnt"] for r in channel_rows}

        failure_type_rows = self._conn.execute(
            "SELECT failure_type, COUNT(*) as cnt FROM leads "
            "WHERE failure_type IS NOT NULL GROUP BY failure_type"
        ).fetchall()
        by_failure = {r["failure_type"]: r["cnt"] for r in failure_type_rows}

        return {
            "total_queries": total,
            "failures": failures,
            "failure_rate": round(failures / total * 100, 1) if total else 0,
            "flagged": flagged,
            "avg_latency_ms": avg_latency,
            "p95_latency_ms": p95_latency,
            "by_channel": by_channel,
            "by_failure_type": by_failure,
        }


# Module-level singleton
_store: Optional[LeadsStore] = None


def get_leads_store() -> LeadsStore:
    global _store
    if _store is None:
        _store = LeadsStore()
    return _store
