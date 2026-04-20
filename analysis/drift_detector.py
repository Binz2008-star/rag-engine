"""Deterministic topic-level drift detector.

Consumes raw events from the event store and aggregates miss-rate signals
per coarse topic. No LLM, no embeddings, no clustering libraries — just
reproducible keyword bucketing over `normalized_query` text.

Signal definition:
    miss = failure_type present
        OR retrieval list empty
        OR answer is a canonical refusal ("Insufficient data.")
    drift_score = miss_count / query_count

Topic assignment is deterministic:
    1. scan the normalized query for the longest matching domain phrase
    2. otherwise fall back to the first non-stopword token
    3. otherwise bucket as "_unknown"
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

from events.store import EventStore, get_store
from router.features import normalize_query

logger = logging.getLogger(__name__)

# Events that represent a terminal per-query outcome. `generation_result`
# is emitted for every handled query and always carries the final
# `failure_type` + `retrieval` fields, so it is the authoritative record.
_TERMINAL_EVENT_TYPE = "generation_result"

# Short, language-agnostic stopword list. Intentionally narrow: we want
# the first meaningful token, not perfect linguistic filtering.
_STOPWORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "did", "do",
    "does", "for", "from", "has", "have", "how", "i", "in", "is", "it",
    "its", "me", "my", "of", "on", "or", "our", "the", "their", "this",
    "to", "was", "we", "were", "what", "when", "where", "which", "who",
    "why", "will", "with", "you", "your",
})

# Domain phrases take precedence over first-token fallback. Kept small and
# human-auditable so drift reports stay explainable. Ordering is enforced
# by phrase length (longest wins) so multi-word phrases are never shadowed
# by a shorter substring phrase — regardless of source declaration order.
_DOMAIN_PHRASES: tuple[tuple[str, str], ...] = tuple(
    sorted(
        [
            ("environmental permit", "environmental_permits"),
            ("environmental compliance", "environmental_compliance"),
            ("wastewater", "wastewater"),
            ("grease trap", "grease_management"),
            ("grease", "grease_management"),
            ("waste management", "waste_management"),
            ("waste", "waste_management"),
            ("municipality", "municipality"),
            ("audit", "audits"),
            ("tender", "tenders"),
            ("certificate", "certificates"),
            ("cv", "cv"),
            ("resume", "cv"),
            ("roben", "cv"),
        ],
        key=lambda item: len(item[0]),
        reverse=True,
    )
)

_TOKEN_RE = re.compile(r"[\w\u0600-\u06FF]+", re.UNICODE)

# Canonical refusal marker emitted by the generation layer. Matching is
# case-insensitive against a stripped prefix so minor punctuation drift
# does not hide a refusal from the drift signal.
_REFUSAL_PREFIX = "insufficient data"


def _extract_topic(normalized_query: str) -> str:
    if not normalized_query:
        return "_unknown"

    for phrase, topic in _DOMAIN_PHRASES:
        if phrase in normalized_query:
            return topic

    for token in _TOKEN_RE.findall(normalized_query):
        if token not in _STOPWORDS and not token.isdigit():
            return token

    return "_unknown"


def _is_refusal(answer: Any) -> bool:
    if not isinstance(answer, str):
        return False
    return answer.strip().lower().startswith(_REFUSAL_PREFIX)


def _is_miss(event: dict[str, Any]) -> bool:
    if event.get("failure_type"):
        return True
    retrieval = event.get("retrieval") or []
    if not retrieval:
        return True
    return _is_refusal(event.get("answer"))


def _classify_action(drift_score: float, miss_count: int, min_misses: int) -> str:
    if miss_count < min_misses:
        return "monitor"
    if drift_score >= 0.5:
        return "add_documents"
    if drift_score >= 0.25:
        return "investigate"
    return "monitor"


def _pick_top_source(counter: Counter[str]) -> str | None:
    if not counter:
        return None
    # Sort by count desc, then source name asc, so ties resolve
    # deterministically across runs and Python versions.
    ranked = sorted(counter.items(), key=lambda kv: (-kv[1], kv[0]))
    return ranked[0][0]


def detect_drift(
    events: Iterable[dict[str, Any]],
    *,
    min_queries: int = 5,
    drift_threshold: float = 0.0,
    min_misses: int = 3,
) -> list[dict[str, Any]]:
    """Aggregate per-topic miss rate from terminal events.

    Args:
        events: iterable of raw event dicts (as stored by `EventStore`).
        min_queries: minimum queries per topic required before it is
            reported. Filters noisy long-tail topics.
        drift_threshold: minimum drift score required to include a topic
            in the output. Use 0.0 to see all qualifying topics.
        min_misses: minimum absolute miss count before `add_documents` /
            `investigate` actions are recommended.

    Returns:
        List of topic drift records sorted by drift_score desc, then by
        miss_count desc. Each record contains `top_missing_source`: the
        source most frequently retrieved in miss events for the topic
        (i.e. the weak nearest-match document), or None if all misses
        had empty retrieval. Deterministic across runs.
    """
    if min_queries < 1:
        raise ValueError("min_queries must be >= 1")
    if not 0.0 <= drift_threshold <= 1.0:
        raise ValueError("drift_threshold must be in [0.0, 1.0]")

    counts: dict[str, dict[str, Any]] = defaultdict(
        lambda: {"queries": 0, "misses": 0, "miss_sources": Counter()}
    )

    for event in events:
        if event.get("event_type") != _TERMINAL_EVENT_TYPE:
            continue

        normalized = event.get("normalized_query")
        if not normalized:
            raw = event.get("query") or ""
            normalized = normalize_query(raw)

        topic = _extract_topic(normalized)
        bucket = counts[topic]
        bucket["queries"] += 1

        if _is_miss(event):
            bucket["misses"] += 1
            for hit in event.get("retrieval") or []:
                source = hit.get("source") if isinstance(hit, dict) else None
                if source:
                    bucket["miss_sources"][source] += 1

    records: list[dict[str, Any]] = []
    for topic, bucket in counts.items():
        queries = bucket["queries"]
        if queries < min_queries:
            continue
        misses = bucket["misses"]
        drift_score = misses / queries if queries else 0.0
        if drift_score < drift_threshold:
            continue
        records.append({
            "topic": topic,
            "query_count": queries,
            "miss_count": misses,
            "drift_score": round(drift_score, 4),
            "action": _classify_action(drift_score, misses, min_misses),
            "top_missing_source": _pick_top_source(bucket["miss_sources"]),
        })

    records.sort(key=lambda r: (-r["drift_score"], -r["miss_count"], r["topic"]))
    return records


def _load_events_from_store(store: EventStore | None = None) -> list[dict[str, Any]]:
    store = store or get_store()
    return store.read_all()


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Detect topic-level retrieval drift from event logs.")
    parser.add_argument("--min-queries", type=int, default=5, help="Minimum queries per topic to report.")
    parser.add_argument("--drift-threshold", type=float, default=0.0, help="Minimum drift score to report.")
    parser.add_argument("--min-misses", type=int, default=3, help="Minimum misses before action is recommended.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to write JSON report.")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    try:
        events = _load_events_from_store()
    except Exception:
        logger.exception("Failed to read event store")
        return 2

    records = detect_drift(
        events,
        min_queries=args.min_queries,
        drift_threshold=args.drift_threshold,
        min_misses=args.min_misses,
    )

    payload = json.dumps(records, indent=2, ensure_ascii=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload, encoding="utf-8")
        logger.info("Drift report written to %s (%d topics)", args.output, len(records))
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    sys.exit(_main())
