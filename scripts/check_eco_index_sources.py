"""
Validate that required eco documents have chunks in models/eco.json.

Exits non-zero if any required source has 0 chunks, signalling that
build_indexes.py must be re-run before the server can serve eco queries.

Usage:
    python scripts/check_eco_index_sources.py
    python scripts/check_eco_index_sources.py --index models/eco.json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REQUIRED_SOURCES = ("pricing.md", "clients.md", "services.md")

DEFAULT_INDEX = Path("models/eco.json")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check that required eco sources have chunks in the index.",
    )
    parser.add_argument(
        "--index",
        type=Path,
        default=DEFAULT_INDEX,
        help=f"Path to eco chunk metadata JSON (default: {DEFAULT_INDEX})",
    )
    args = parser.parse_args(argv)

    index_path: Path = args.index

    if not index_path.exists():
        print(f"FAIL: index file not found at {index_path}")
        return 1

    with index_path.open(encoding="utf-8") as f:
        chunks = json.load(f)

    if not isinstance(chunks, list):
        print(f"FAIL: expected JSON list, got {type(chunks).__name__}")
        return 1

    # Count chunks per source (normalise to basename)
    source_counts: dict[str, int] = {}
    for chunk in chunks:
        src = Path(chunk.get("source", "")).name
        source_counts[src] = source_counts.get(src, 0) + 1

    # Report
    print(f"Eco index: {index_path}  ({len(chunks)} total chunks)")
    print()

    ok = True
    for required in REQUIRED_SOURCES:
        count = source_counts.get(required, 0)
        status = "OK" if count > 0 else "MISSING"
        print(f"  {required:<20s}  chunks={count:<4d}  [{status}]")
        if count == 0:
            ok = False

    # Also show other sources present (informational)
    others = sorted(
        (src, cnt)
        for src, cnt in source_counts.items()
        if src not in REQUIRED_SOURCES
    )
    if others:
        print()
        print("  Other sources in eco index:")
        for src, cnt in others:
            print(f"    {src:<40s}  chunks={cnt}")

    print()
    if ok:
        print(f"PASS: all {len(REQUIRED_SOURCES)} required sources present")
        return 0

    missing = [s for s in REQUIRED_SOURCES if source_counts.get(s, 0) == 0]
    print(
        f"FAIL: {len(missing)} required source(s) missing: "
        + ", ".join(missing)
    )
    print("Run:  python scripts/build_indexes.py --debug")
    return 1


if __name__ == "__main__":
    sys.exit(main())
