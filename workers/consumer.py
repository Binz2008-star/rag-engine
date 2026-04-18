from __future__ import annotations

from events.replay import load_events


def iter_events() -> list[dict]:
    return load_events()
