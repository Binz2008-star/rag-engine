from __future__ import annotations

import json
import sqlite3

from app.config import LOG_DIR

DB = LOG_DIR / "events.db"


def load_events() -> list[dict]:
    conn = sqlite3.connect(DB)
    rows = conn.execute("SELECT payload FROM events ORDER BY ts ASC").fetchall()
    return [json.loads(row[0]) for row in rows]


def replay_queries(pipeline) -> list[dict]:
    results: list[dict] = []
    for event in load_events():
        if event.get("event_type") == "query_received":
            results.append(pipeline.run(query=event["query"], query_id=event["query_id"]))
    return results
