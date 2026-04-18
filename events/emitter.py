from __future__ import annotations

import time

from app.config import EVENT_SCHEMA_VERSION
from events.store import get_store


def emit_event(event: dict) -> None:
    payload = {
        "version": EVENT_SCHEMA_VERSION,
        "ts": time.time(),
        **event,
    }
    store = get_store()
    store.write(payload)
