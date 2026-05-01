from __future__ import annotations

import json
import sqlite3
import threading
from pathlib import Path
from typing import Any

from app.config import EVENT_DB_PATH
from events.schema import validate_event


class EventStore:
    def __init__(self, db_path: Path = EVENT_DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._lock = threading.RLock()  # Guards all SQLite operations
        self._init_schema()

    def _init_schema(self):
        with self._lock:
            self.conn.execute("""
                CREATE TABLE IF NOT EXISTS events (
                    ts REAL,
                    version TEXT,
                    event_type TEXT,
                    query_id TEXT,
                    payload TEXT
                )
            """)
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_ts ON events(ts)")
            self.conn.execute("CREATE INDEX IF NOT EXISTS idx_query ON events(query_id)")
            self.conn.commit()

    def write(self, event: dict[str, Any]) -> None:
        validate_event(event)
        with self._lock:
            self.conn.execute(
                "INSERT INTO events VALUES (?,?,?,?,?)",
                (event["ts"], event["version"], event["event_type"], event["query_id"], json.dumps(event)),
            )
            self.conn.commit()

    def read_all(self) -> list[dict]:
        with self._lock:
            rows = self.conn.execute("SELECT payload FROM events ORDER BY ts").fetchall()
        return [json.loads(r[0]) for r in rows]


_store = None

def get_store() -> EventStore:
    global _store
    if _store is None:
        _store = EventStore()
    return _store
