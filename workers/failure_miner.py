from __future__ import annotations

from collections import Counter

from workers.consumer import iter_events


def mine_failures() -> dict[str, int]:
    events = iter_events()
    failures = [event for event in events if event.get("event_type") == "failure"]
    counts = Counter(event.get("failure_type", "unknown") for event in failures)
    return dict(counts)
