"""
merge_eval_queries.py — safe merge of eval query batches.

Features
--------
* Deduplicates against the existing suite (normalised text match).
* Validates schema against the canonical gate contract:
    - required: `query`, `suite`
    - `expected_intent` restricted to the INTENT_CLASSES enum
    - killer rows must declare a hard assertion
    - refusal rows must align on the canonical `Insufficient data.` token
    - hedging-only `must_not_contain` is flagged as a weak assertion
    - short tokens (<3 chars) in `must_not_contain` flagged as fragile
    - single-token `expected_answer_contains` flagged as non-discriminating
* Accepts both short-name (`expected_exact`, `expected_contains`) and long-name
  (`expected_answer_exact`, `expected_answer_contains`) schemas so either
  evaluator path can consume the output. Short names are upgraded to the long
  canonical form on write, matching `tests/eval_queries.json`.
* Atomic write with automatic `.bak` backup — the canonical suite is never
  left in a partially-written state.
* Optional `--strict` promotes all warnings to errors.

Usage
-----
    python scripts/merge_eval_queries.py \\
        --existing tests/eval_queries.json \\
        --new tests/new_eval_queries.json \\
        --output tests/eval_queries.json \\
        [--dry-run] [--strict] [--no-backup]
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

logger = logging.getLogger("merge_eval_queries")

# ── Canonical contract ──────────────────────────────────────────────────────
# Kept in sync with app.config.REFUSAL_MESSAGE and app.config.INTENT_CLASSES.
# Duplicated here on purpose: the merge script must stay runnable as a plain
# tooling entry point without importing the application package.
REFUSAL_MESSAGE = "Insufficient data."
INTENT_CLASSES = frozenset({"cv", "eco", "general"})
REQUIRED_FIELDS = frozenset({"query", "suite"})
HEDGING_PHRASES = frozenset({
    "appears to be", "can be inferred", "based on context",
    "I think", "I assume", "I believe", "probably", "possibly",
    "يبدو أن", "يمكن الاستنتاج", "بناءً على السياق",
})
ASSERTION_FIELDS = frozenset({
    "expected_refusal",
    "expected_exact",
    "expected_answer_exact",
    "expected_contains",
    "expected_answer_contains",
    "must_not_contain",
    "must_be_grounded",
    "expected_failure_type",
})
HARD_ASSERTION_FIELDS = frozenset({
    "expected_refusal",
    "expected_exact",
    "expected_answer_exact",
    "expected_contains",
    "expected_answer_contains",
    "expected_failure_type",
})

# Alias map: short → long (long is canonical on-disk per existing suite).
ALIAS_SHORT_TO_LONG: dict[str, str] = {
    "expected_exact": "expected_answer_exact",
    "expected_contains": "expected_answer_contains",
}

FRAGILE_TOKEN_MIN_LEN = 3


# ── Normalisation ───────────────────────────────────────────────────────────

def normalise_query_text(text: str) -> str:
    return " ".join(text.strip().lower().split())


def normalise_schema(q: dict[str, Any]) -> dict[str, Any]:
    """Promote short-name aliases to the canonical long-name form.

    Conflicts (both aliases present with different values) are reported via
    the caller's validation pass, not silently resolved here.
    """
    out = dict(q)
    for short, long_ in ALIAS_SHORT_TO_LONG.items():
        if short in out and long_ not in out:
            out[long_] = out.pop(short)
        elif short in out and long_ in out:
            # Leave both in place; validator will raise.
            pass
    return out


# ── Validation ──────────────────────────────────────────────────────────────

def _has_hard_assertion(q: dict[str, Any]) -> bool:
    return any(q.get(f) not in (None, "", [], False) for f in HARD_ASSERTION_FIELDS)


def _is_hedging_only(must_not_contain: list[Any]) -> bool:
    if not must_not_contain:
        return False
    return all(isinstance(t, str) and t in HEDGING_PHRASES for t in must_not_contain)


def validate_query(q: dict[str, Any], index: int) -> tuple[list[str], list[str]]:
    """Return (errors, warnings) for a single query row."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(q, dict):
        return [f"[{index}] not an object"], []

    # --- Required ---
    missing = REQUIRED_FIELDS - set(q.keys())
    if missing:
        errors.append(f"[{index}] missing required fields: {sorted(missing)}")

    query_text = q.get("query")
    if not isinstance(query_text, str) or not query_text.strip():
        errors.append(f"[{index}] empty or non-string 'query'")

    # --- Alias conflicts ---
    for short, long_ in ALIAS_SHORT_TO_LONG.items():
        if short in q and long_ in q and q[short] != q[long_]:
            errors.append(
                f"[{index}] conflicting aliases {short!r} and {long_!r} have "
                f"different values"
            )

    # --- Intent enum ---
    intent = q.get("expected_intent")
    if intent is not None and intent not in INTENT_CLASSES:
        errors.append(
            f"[{index}] expected_intent={intent!r} not in {sorted(INTENT_CLASSES)}"
        )

    # --- Testable assertion ---
    if not any(q.get(f) not in (None, "", [], False) for f in ASSERTION_FIELDS):
        errors.append(
            f"[{index}] no testable assertion: "
            f"{(query_text or '')[:60]!r}"
        )

    # --- Refusal canonicalisation ---
    expected_refusal = q.get("expected_refusal") is True
    exact_val = q.get("expected_answer_exact", q.get("expected_exact"))
    if expected_refusal and exact_val not in (None, REFUSAL_MESSAGE):
        errors.append(
            f"[{index}] expected_refusal=true requires expected_answer_exact="
            f"{REFUSAL_MESSAGE!r} (got {exact_val!r})"
        )
    if expected_refusal and exact_val is None:
        warnings.append(
            f"[{index}] expected_refusal=true without expected_answer_exact — "
            f"consider adding {REFUSAL_MESSAGE!r} for determinism"
        )

    # --- Killer rows must be hard to pass by accident ---
    if q.get("killer") is True and not _has_hard_assertion(q):
        errors.append(
            f"[{index}] killer=true but no hard assertion "
            f"(expected_refusal / expected_answer_* / expected_failure_type)"
        )

    # --- Hedging-only must_not_contain is a weak assertion ---
    mnc = q.get("must_not_contain") or []
    if _is_hedging_only(mnc):
        other_hard = any(
            q.get(f) not in (None, "", [], False)
            for f in HARD_ASSERTION_FIELDS
        )
        if not other_hard:
            warnings.append(
                f"[{index}] must_not_contain contains only hedging phrases — "
                f"add a hard assertion: {(query_text or '')[:60]!r}"
            )

    # --- Fragile short tokens in must_not_contain ---
    fragile = [
        t for t in mnc
        if isinstance(t, str) and len(t) < FRAGILE_TOKEN_MIN_LEN
    ]
    if fragile:
        warnings.append(
            f"[{index}] fragile short tokens in must_not_contain "
            f"(substring match will false-positive): {fragile}"
        )

    # --- Single-token expected_answer_contains is non-discriminating ---
    contains_val = q.get("expected_answer_contains", q.get("expected_contains"))
    if isinstance(contains_val, list) and len(contains_val) == 1:
        token = contains_val[0]
        if isinstance(token, str) and len(token) <= 4:
            warnings.append(
                f"[{index}] single short anchor in expected_answer_contains="
                f"{contains_val!r} — consider multi-token anchor"
            )

    return errors, warnings


def validate_all(
    queries: list[dict[str, Any]],
    label: str,
    strict: bool,
) -> tuple[bool, int]:
    """Run validation and return (is_valid, warning_count)."""
    all_errors: list[str] = []
    all_warnings: list[str] = []
    for i, q in enumerate(queries):
        errs, warns = validate_query(q, i)
        all_errors.extend(errs)
        all_warnings.extend(warns)

    if all_warnings:
        logger.warning("[%s] %d warning(s):", label, len(all_warnings))
        for w in all_warnings:
            logger.warning("  %s", w)

    if all_errors:
        logger.error("[%s] %d error(s):", label, len(all_errors))
        for e in all_errors:
            logger.error("  %s", e)
        return False, len(all_warnings)

    if strict and all_warnings:
        logger.error("[%s] strict mode: warnings treated as errors", label)
        return False, len(all_warnings)

    return True, len(all_warnings)


# ── Dedup ──────────────────────────────────────────────────────────────────

def deduplicate(
    existing: list[dict[str, Any]],
    new: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], int, int]:
    """Return (clean_new, added, skipped).

    Skipped queries are either exact-text duplicates (after whitespace/case
    normalisation) or have an empty query field (the latter is also a
    validation error, so the caller decides whether to proceed).
    """
    seen = {normalise_query_text(q["query"]) for q in existing if isinstance(q.get("query"), str)}
    clean: list[dict[str, Any]] = []
    skipped = 0
    for q in new:
        text = q.get("query")
        if not isinstance(text, str) or not text.strip():
            skipped += 1
            continue
        key = normalise_query_text(text)
        if key in seen:
            skipped += 1
            continue
        clean.append(q)
        seen.add(key)
    return clean, len(clean), skipped


# ── Atomic write + backup ──────────────────────────────────────────────────

def atomic_write_json(path: Path, data: Any, *, backup: bool) -> Path | None:
    """Write JSON atomically. Returns the backup path if one was created."""
    path.parent.mkdir(parents=True, exist_ok=True)

    backup_path: Path | None = None
    if backup and path.exists():
        backup_path = path.with_suffix(path.suffix + ".bak")
        # Fresh backup each run — we keep a single rolling copy.
        backup_path.write_bytes(path.read_bytes())

    fd, tmp_name = tempfile.mkstemp(
        prefix=path.name + ".",
        suffix=".tmp",
        dir=str(path.parent),
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
        # Atomic on POSIX; best-effort on Windows via os.replace().
        os.replace(tmp_name, path)
    except Exception:
        # Best-effort cleanup of the temp file on failure.
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise

    return backup_path


# ── Summary reporting ──────────────────────────────────────────────────────

def print_summary(merged: list[dict[str, Any]]) -> None:
    suites = Counter(q.get("suite", "unknown") for q in merged)
    killers = sum(1 for q in merged if q.get("killer") is True)
    refusals = sum(1 for q in merged if q.get("expected_refusal") is True)

    logger.info("merged total : %d", len(merged))
    logger.info("  killers    : %d", killers)
    logger.info("  refusals   : %d", refusals)
    logger.info("  by suite:")
    for suite, count in sorted(suites.items()):
        logger.info("    %s: %d", suite, count)


# ── CLI ────────────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Merge eval query files with dedup + schema validation.",
    )
    parser.add_argument("--existing", required=True, type=Path)
    parser.add_argument("--new", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print stats without writing the output file.",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="Treat validation warnings as errors.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip writing a .bak sidecar when overwriting the output.",
    )
    parser.add_argument(
        "--skip-validation",
        action="store_true",
        help="Merge even if validation fails (not recommended).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable debug logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(name)s: %(message)s",
    )

    # --- Load ---
    try:
        existing_raw: Any = json.loads(args.existing.read_text(encoding="utf-8"))
        new_raw: Any = json.loads(args.new.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, FileNotFoundError, OSError) as exc:
        logger.error("failed to load input files: %s", exc)
        return 2

    if not isinstance(existing_raw, list) or not isinstance(new_raw, list):
        logger.error("both input files must be JSON arrays")
        return 2

    # Normalise alias fields before any further processing.
    existing = [normalise_schema(q) if isinstance(q, dict) else q for q in existing_raw]
    new_queries = [normalise_schema(q) if isinstance(q, dict) else q for q in new_raw]

    logger.info("existing queries : %d", len(existing))
    logger.info("new queries      : %d", len(new_queries))

    # --- Validate NEW batch ---
    ok_new, _ = validate_all(new_queries, "new queries", args.strict)
    if not ok_new and not args.skip_validation:
        logger.error("aborted: fix validation errors before merging")
        return 1

    # --- Sanity-check existing suite too (non-blocking unless --strict) ---
    ok_existing, _ = validate_all(existing, "existing suite", args.strict)
    if not ok_existing and args.strict and not args.skip_validation:
        logger.error("aborted: existing suite has errors under --strict")
        return 1

    # --- Dedup ---
    clean_new, added, skipped = deduplicate(existing, new_queries)
    logger.info("dedup: added=%d skipped=%d", added, skipped)

    merged = existing + clean_new
    print_summary(merged)

    # --- Killer invariant: the CI gate requires ≥1 killer. Refuse to
    # write a merged suite that would reduce the killer count below the
    # existing baseline. ---
    existing_killers = sum(1 for q in existing if q.get("killer") is True)
    merged_killers = sum(1 for q in merged if q.get("killer") is True)
    if merged_killers < existing_killers:
        logger.error(
            "merged suite killer count (%d) is below existing baseline (%d); refusing to write",
            merged_killers, existing_killers,
        )
        return 1

    if args.dry_run:
        logger.info("dry-run: no files written")
        return 0

    try:
        backup = atomic_write_json(
            args.output,
            merged,
            backup=not args.no_backup,
        )
    except OSError as exc:
        logger.error("failed to write %s: %s", args.output, exc)
        return 2

    logger.info("wrote %d queries to %s", len(merged), args.output)
    if backup is not None:
        logger.info("backup saved to %s", backup)
    return 0


if __name__ == "__main__":
    sys.exit(main())
