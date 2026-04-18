from __future__ import annotations

import json
import sqlite3
import time

from app.config import EVENT_SCHEMA_VERSION, LOG_DIR
from events.schema import validate_event

DB = LOG_DIR / "events.db"
CONN = sqlite3.connect(DB, check_same_thread=False)
CONN.execute(
    """
    CREATE TABLE IF NOT EXISTS events (
        ts REAL,
        version TEXT,
        event_type TEXT,
        query_id TEXT,
        payload TEXT
    )
    """
)
CONN.commit()


def emit(event_type: str, payload: dict) -> None:
    event = {
        "version": EVENT_SCHEMA_VERSION,
        "ts": time.time(),
        "event_type": event_type,
        **payload,
    }
    validate_event(event)
    CONN.execute(
        "INSERT INTO events VALUES (?,?,?,?,?)",
        (
            event["ts"],
            event["version"],
            event["event_type"],
            event["query_id"],
            json.dumps(event, ensure_ascii=False),
        ),
    )
    CONN.commit()


def emit_event(event: dict) -> None:
    payload = dict(event)
    event_type = payload.pop("event_type")
    emit(event_type, payload)
