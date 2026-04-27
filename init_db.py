"""Initialize database tables for Robin AI Pipeline."""

from __future__ import annotations

import os
from pathlib import Path

import psycopg2


DATABASE_URL = os.environ.get("DATABASE_URL")


def init_database() -> None:
    """Create database tables from init_db.sql."""
    if not DATABASE_URL:
        raise RuntimeError("DATABASE_URL environment variable is required")

    sql_path = Path(__file__).with_name("init_db.sql")
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")

    with psycopg2.connect(DATABASE_URL) as conn:
        with conn.cursor() as cur:
            cur.execute(sql_path.read_text(encoding="utf-8"))

    print("Database tables created successfully")


if __name__ == "__main__":
    init_database()
