"""
aggregate_reports.py
--------------------
Cross-run decision dashboard for the strict eval pipeline.

Consumes the JSON reports emitted by `eval_runner.py` (see
`reports/ci_eval_strict*.json`) and produces:

  1. A single aggregate JSON with:
       - `runs`     : canonical per-run summary (chronological)
       - `trend`    : time-series for key gate metrics
       - `failures` : cross-run failure-bucket counts
       - `intent`   : intent-router accuracy trend
       - `latest`   : the most recent run summary
       - `regression`: automated regression flags (latest vs previous)

  2. (Optional) a Markdown summary suited for
     `$GITHUB_STEP_SUMMARY` in CI.

Design notes
------------
- **No coupling** to external configs (no YAML, no model registry).
  The only contract is the report schema already written by
  `eval_runner.py` + `evaluation/eval_gate.py`.
- **Deterministic ordering**: reports are ordered by file mtime,
  with a stable tiebreaker on filename. No reliance on wall-clock
  timestamps embedded in the report (they are not emitted today).
- **Fail-closed regression detection**: a configurable threshold
  set catches the common regressions the gate does not block on
  its own (e.g. latency drift, failure-bucket reshuffles).

Exit codes
----------
    0  success (or success with no regressions, if `--fail-on-regression`)
    1  regression detected AND `--fail-on-regression` was set
    2  usage / IO error
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

logger = logging.getLogger("aggregate_reports")

# ── Report schema constants ──────────────────────────────────────────────────
# Canonical metric keys emitted by eval_runner / eval_gate. Keeping them
# centralised makes it a single-line change if the gate ever renames one.
METRIC_KEYS_RATE: tuple[str, ...] = (
    "pass_rate",
    "real_pass_rate",
    "hallucination_rate",
    "refusal_accuracy",
    "domain_accuracy",
)
METRIC_KEYS_COUNT: tuple[str, ...] = (
    "total",
    "passed",
    "failed",
    "errors",
    "low_conf_failures",
    "corpus_missing_count",
    "generic_answer_count",
)
LATENCY_KEY = "avg_elapsed_s"
SLA_KEYS: tuple[str, ...] = ("latency_sla_ms", "sla_pass")
PROMOTE_DECISION = "PROMOTE"

# Regression thresholds. Deliberately conservative — the gate is the
# authoritative accept/reject; this script flags directional drift that
# merits a human look even when the gate is still green.
DEFAULT_PASS_RATE_DROP = 0.01           # 1 percentage point
DEFAULT_DOMAIN_ACC_DROP = 0.01
DEFAULT_REFUSAL_ACC_DROP = 0.0          # any drop from 1.0 is a regression
DEFAULT_HALLUCINATION_RISE = 0.0        # any positive hallucination is a regression
DEFAULT_LATENCY_RISE_RATIO = 0.20       # +20 % over previous run


# ── Data classes ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RunSummary:
    """Canonical, flat summary of one eval report."""

    run_id: str
    source_path: str
    mtime_utc: str
    decision: str | None
    failed_checks: list[str]
    metrics: dict[str, Any]
    failure_buckets: dict[str, int]
    intent_type_accuracy: dict[str, float]
    intent_method_accuracy: dict[str, float]
    killer_failures: int
    regression_failures: int  # non-killer, non-passing rows

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class RegressionFlags:
    """Structured diff between the latest run and its predecessor."""

    has_regression: bool = False
    decision_flipped: bool = False
    reasons: list[str] = field(default_factory=list)
    deltas: dict[str, float] = field(default_factory=dict)
    new_failure_buckets: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# ── IO ───────────────────────────────────────────────────────────────────────

def _load_report(path: Path) -> dict[str, Any]:
    """Load a single report, tolerating malformed files with a warning."""
    try:
        with path.open("r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError) as exc:
        logger.warning("Skipping unreadable report %s: %s", path, exc)
        return {}
    if not isinstance(data, dict):
        logger.warning("Skipping non-dict report %s", path)
        return {}
    return data


def _discover_reports(
    reports_dir: Path,
    pattern: str,
    exclude: Iterable[Path] = (),
) -> list[Path]:
    """Find report files matching `pattern` under `reports_dir`.

    Ordering: by mtime ascending, ties broken by filename for determinism.
    Aggregation outputs are excluded so re-runs do not ingest themselves.
    """
    if not reports_dir.is_dir():
        raise FileNotFoundError(f"reports dir not found: {reports_dir}")

    exclude_resolved = {p.resolve() for p in exclude}
    candidates = [
        p for p in reports_dir.glob(pattern)
        if p.is_file() and p.resolve() not in exclude_resolved
    ]
    candidates.sort(key=lambda p: (p.stat().st_mtime, p.name))
    return candidates


# ── Report → summary ─────────────────────────────────────────────────────────

def _safe_float(value: Any, default: float = 0.0) -> float:
    """Coerce to float, returning `default` for None/invalid values."""
    if value is None:
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: Any, default: int = 0) -> int:
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _extract_intent_accuracy(block: Any) -> dict[str, float]:
    """Pull `{key: accuracy}` from an `intent_*_metrics` sub-dict."""
    if not isinstance(block, dict):
        return {}
    out: dict[str, float] = {}
    for name, stats in block.items():
        if isinstance(stats, dict) and "accuracy" in stats:
            out[str(name)] = _safe_float(stats["accuracy"])
    return out


def _count_killer_failures(results: list[Any]) -> int:
    return sum(
        1
        for r in results
        if isinstance(r, dict) and r.get("killer") is True and r.get("passed") is not True
    )


def _count_regression_failures(results: list[Any]) -> int:
    return sum(
        1
        for r in results
        if isinstance(r, dict) and r.get("killer") is not True and r.get("passed") is False
    )


def _derive_run_id(path: Path) -> str:
    """
    Use filename stem as the stable run identifier. The eval runner writes
    names like `ci_eval_strict_track1b.json` or `eval_<epoch>.json`, both
    of which are already unique per run.
    """
    return path.stem


def summarize_report(path: Path, raw: dict[str, Any]) -> RunSummary:
    metrics_raw = raw.get("metrics") or {}
    results_raw = raw.get("results") or []

    # Flatten the subset of metrics we track. Missing keys become None so
    # downstream consumers can distinguish "not measured" from 0.
    flat_metrics: dict[str, Any] = {}
    for key in METRIC_KEYS_RATE + METRIC_KEYS_COUNT:
        flat_metrics[key] = metrics_raw.get(key)
    flat_metrics[LATENCY_KEY] = metrics_raw.get(LATENCY_KEY)
    for key in SLA_KEYS:
        flat_metrics[key] = metrics_raw.get(key)

    failure_buckets = metrics_raw.get("failure_buckets") or {}
    if not isinstance(failure_buckets, dict):
        failure_buckets = {}
    # Normalise to int to protect against stray floats/strings.
    failure_buckets = {str(k): _safe_int(v) for k, v in failure_buckets.items()}

    mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)

    return RunSummary(
        run_id=_derive_run_id(path),
        source_path=str(path),
        mtime_utc=mtime.isoformat(),
        decision=raw.get("decision"),
        failed_checks=list(raw.get("failed_checks") or []),
        metrics=flat_metrics,
        failure_buckets=failure_buckets,
        intent_type_accuracy=_extract_intent_accuracy(metrics_raw.get("intent_type_metrics")),
        intent_method_accuracy=_extract_intent_accuracy(metrics_raw.get("intent_method_metrics")),
        killer_failures=_count_killer_failures(results_raw),
        regression_failures=_count_regression_failures(results_raw),
    )


# ── Trend + failure aggregation ──────────────────────────────────────────────

def build_trend(runs: list[RunSummary]) -> dict[str, list[Any]]:
    """Per-metric time series aligned to `runs` order."""
    trend: dict[str, list[Any]] = {"run_id": [r.run_id for r in runs]}

    for key in METRIC_KEYS_RATE + METRIC_KEYS_COUNT + (LATENCY_KEY,):
        trend[key] = [r.metrics.get(key) for r in runs]

    trend["decision"] = [r.decision for r in runs]
    trend["killer_failures"] = [r.killer_failures for r in runs]
    trend["sla_pass"] = [r.metrics.get("sla_pass") for r in runs]
    return trend


def build_failure_aggregate(runs: list[RunSummary]) -> dict[str, Any]:
    """Total counts per failure bucket and per-run breakdown."""
    totals: dict[str, int] = {}
    per_run: dict[str, dict[str, int]] = {}
    for r in runs:
        per_run[r.run_id] = dict(r.failure_buckets)
        for bucket, count in r.failure_buckets.items():
            totals[bucket] = totals.get(bucket, 0) + count
    return {"totals": totals, "per_run": per_run}


def build_intent_trend(runs: list[RunSummary]) -> dict[str, Any]:
    """Track intent-router accuracy per type and per method across runs."""
    types: dict[str, list[float | None]] = {}
    methods: dict[str, list[float | None]] = {}

    all_types = {t for r in runs for t in r.intent_type_accuracy}
    all_methods = {m for r in runs for m in r.intent_method_accuracy}

    for t in sorted(all_types):
        types[t] = [r.intent_type_accuracy.get(t) for r in runs]
    for m in sorted(all_methods):
        methods[m] = [r.intent_method_accuracy.get(m) for r in runs]

    return {"by_type": types, "by_method": methods}


# ── Regression detection ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class RegressionThresholds:
    pass_rate_drop: float = DEFAULT_PASS_RATE_DROP
    domain_accuracy_drop: float = DEFAULT_DOMAIN_ACC_DROP
    refusal_accuracy_drop: float = DEFAULT_REFUSAL_ACC_DROP
    hallucination_rise: float = DEFAULT_HALLUCINATION_RISE
    latency_rise_ratio: float = DEFAULT_LATENCY_RISE_RATIO


def detect_regression(
    latest: RunSummary,
    previous: RunSummary | None,
    thresholds: RegressionThresholds,
) -> RegressionFlags:
    flags = RegressionFlags()
    if previous is None:
        return flags

    def _delta_rate(key: str) -> float:
        before = _safe_float(previous.metrics.get(key))
        after = _safe_float(latest.metrics.get(key))
        delta = after - before
        flags.deltas[key] = round(delta, 6)
        return delta

    # --- Decision flip ---
    if previous.decision == PROMOTE_DECISION and latest.decision != PROMOTE_DECISION:
        flags.decision_flipped = True
        flags.has_regression = True
        flags.reasons.append(
            f"decision flipped: {previous.decision} -> {latest.decision}"
        )

    # --- Rate metrics: drops ---
    pass_delta = _delta_rate("pass_rate")
    if pass_delta < -thresholds.pass_rate_drop:
        flags.has_regression = True
        flags.reasons.append(
            f"pass_rate dropped by {-pass_delta:.3f} "
            f"(> threshold {thresholds.pass_rate_drop})"
        )

    domain_delta = _delta_rate("domain_accuracy")
    if domain_delta < -thresholds.domain_accuracy_drop:
        flags.has_regression = True
        flags.reasons.append(
            f"domain_accuracy dropped by {-domain_delta:.3f} "
            f"(> threshold {thresholds.domain_accuracy_drop})"
        )

    refusal_delta = _delta_rate("refusal_accuracy")
    if refusal_delta < -thresholds.refusal_accuracy_drop and refusal_delta < 0:
        flags.has_regression = True
        flags.reasons.append(
            f"refusal_accuracy dropped by {-refusal_delta:.3f}"
        )

    # --- Hallucination: any rise is a regression ---
    halluc_delta = _delta_rate("hallucination_rate")
    if halluc_delta > thresholds.hallucination_rise:
        flags.has_regression = True
        flags.reasons.append(
            f"hallucination_rate rose by {halluc_delta:.3f}"
        )

    # --- Latency: relative rise ---
    before_lat = _safe_float(previous.metrics.get(LATENCY_KEY))
    after_lat = _safe_float(latest.metrics.get(LATENCY_KEY))
    flags.deltas[LATENCY_KEY] = round(after_lat - before_lat, 6)
    if before_lat > 0 and after_lat > before_lat * (1 + thresholds.latency_rise_ratio):
        flags.has_regression = True
        ratio = (after_lat - before_lat) / before_lat
        flags.reasons.append(
            f"{LATENCY_KEY} rose by {ratio:.1%} "
            f"({before_lat:.2f}s -> {after_lat:.2f}s)"
        )

    # --- New failure buckets ---
    prev_buckets = set(previous.failure_buckets)
    new_buckets = sorted(set(latest.failure_buckets) - prev_buckets)
    if new_buckets:
        flags.new_failure_buckets = new_buckets
        flags.has_regression = True
        flags.reasons.append(
            f"new failure buckets: {', '.join(new_buckets)}"
        )

    # --- Killer failures appearing ---
    if latest.killer_failures > previous.killer_failures:
        flags.has_regression = True
        flags.reasons.append(
            f"killer_failures rose "
            f"{previous.killer_failures} -> {latest.killer_failures}"
        )

    return flags


# ── Markdown renderer (CI step summary) ──────────────────────────────────────

def _fmt_pct(v: Any) -> str:
    if v is None:
        return "n/a"
    return f"{_safe_float(v) * 100:.1f}%"


def _fmt_secs(v: Any) -> str:
    if v is None:
        return "n/a"
    return f"{_safe_float(v):.2f}s"


def render_markdown(
    runs: list[RunSummary],
    regression: RegressionFlags,
) -> str:
    if not runs:
        return "# Eval Aggregate\n\nNo reports found.\n"

    latest = runs[-1]
    previous = runs[-2] if len(runs) >= 2 else None

    lines: list[str] = []
    lines.append("# Eval Aggregate Summary")
    lines.append("")
    lines.append(f"- Runs aggregated: **{len(runs)}**")
    lines.append(f"- Latest run: `{latest.run_id}` "
                 f"(decision: **{latest.decision or 'UNKNOWN'}**)")
    if previous:
        lines.append(f"- Previous run: `{previous.run_id}` "
                     f"(decision: **{previous.decision or 'UNKNOWN'}**)")
    lines.append("")

    # --- Key metrics table (latest vs previous) ---
    lines.append("## Key metrics (latest vs previous)")
    lines.append("")
    lines.append("| Metric | Previous | Latest | Δ |")
    lines.append("|---|---|---|---|")

    def _row_rate(label: str, key: str) -> str:
        prev_v = previous.metrics.get(key) if previous else None
        last_v = latest.metrics.get(key)
        delta = ""
        if prev_v is not None and last_v is not None:
            d = (_safe_float(last_v) - _safe_float(prev_v)) * 100
            delta = f"{d:+.2f} pp"
        return f"| {label} | {_fmt_pct(prev_v)} | {_fmt_pct(last_v)} | {delta} |"

    lines.append(_row_rate("Pass rate", "pass_rate"))
    lines.append(_row_rate("Real pass rate", "real_pass_rate"))
    lines.append(_row_rate("Hallucination rate", "hallucination_rate"))
    lines.append(_row_rate("Refusal accuracy", "refusal_accuracy"))
    lines.append(_row_rate("Domain accuracy", "domain_accuracy"))

    prev_lat = previous.metrics.get(LATENCY_KEY) if previous else None
    last_lat = latest.metrics.get(LATENCY_KEY)
    lat_delta = ""
    if prev_lat is not None and last_lat is not None and _safe_float(prev_lat) > 0:
        ratio = (_safe_float(last_lat) - _safe_float(prev_lat)) / _safe_float(prev_lat)
        lat_delta = f"{ratio:+.1%}"
    lines.append(f"| Avg latency | {_fmt_secs(prev_lat)} | {_fmt_secs(last_lat)} | {lat_delta} |")
    lines.append("")

    # --- Failure buckets ---
    if latest.failure_buckets:
        lines.append("## Failure buckets (latest)")
        lines.append("")
        lines.append("| Bucket | Count |")
        lines.append("|---|---|")
        for bucket, count in sorted(latest.failure_buckets.items(),
                                    key=lambda kv: -kv[1]):
            lines.append(f"| `{bucket}` | {count} |")
        lines.append("")

    # --- Regression block ---
    lines.append("## Regression check")
    lines.append("")
    if regression.has_regression:
        lines.append("**REGRESSION DETECTED**")
        lines.append("")
        for reason in regression.reasons:
            lines.append(f"- {reason}")
    else:
        lines.append("No regressions against previous run.")
    lines.append("")

    return "\n".join(lines)


# ── Orchestration ────────────────────────────────────────────────────────────

def aggregate(
    reports_dir: Path,
    pattern: str,
    output: Path,
    window: int,
    thresholds: RegressionThresholds,
) -> tuple[dict[str, Any], RegressionFlags, list[RunSummary]]:
    paths = _discover_reports(reports_dir, pattern, exclude=[output])
    if window > 0:
        paths = paths[-window:]

    runs: list[RunSummary] = []
    for p in paths:
        raw = _load_report(p)
        if not raw:
            continue
        runs.append(summarize_report(p, raw))

    previous = runs[-2] if len(runs) >= 2 else None
    latest = runs[-1] if runs else None
    regression = (
        detect_regression(latest, previous, thresholds)
        if latest is not None
        else RegressionFlags()
    )

    aggregate_doc: dict[str, Any] = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "reports_dir": str(reports_dir),
        "pattern": pattern,
        "count": len(runs),
        "runs": [r.to_dict() for r in runs],
        "trend": build_trend(runs),
        "failures": build_failure_aggregate(runs),
        "intent": build_intent_trend(runs),
        "latest": runs[-1].to_dict() if runs else None,
        "regression": regression.to_dict(),
    }
    return aggregate_doc, regression, runs


# ── CLI ──────────────────────────────────────────────────────────────────────

def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Aggregate strict-eval JSON reports into a single decision "
            "artefact with trend and regression signals."
        ),
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=Path("reports"),
        help="Directory containing eval reports (default: reports)",
    )
    parser.add_argument(
        "--pattern",
        type=str,
        default="ci_eval_strict*.json",
        help="Glob pattern for report files (default: ci_eval_strict*.json)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("reports/aggregate.json"),
        help="Path for aggregate JSON output (default: reports/aggregate.json)",
    )
    parser.add_argument(
        "--window",
        type=int,
        default=0,
        help="Limit to the latest N reports (0 = all, default: 0)",
    )
    parser.add_argument(
        "--markdown",
        type=Path,
        default=None,
        help=(
            "Optional path to write a Markdown summary "
            "(suitable for $GITHUB_STEP_SUMMARY)."
        ),
    )
    parser.add_argument(
        "--fail-on-regression",
        action="store_true",
        help="Exit 1 if a regression is detected vs the previous run.",
    )
    parser.add_argument(
        "--pass-rate-drop",
        type=float,
        default=DEFAULT_PASS_RATE_DROP,
        help="Regression threshold for pass_rate drop (default: 0.01).",
    )
    parser.add_argument(
        "--domain-accuracy-drop",
        type=float,
        default=DEFAULT_DOMAIN_ACC_DROP,
        help="Regression threshold for domain_accuracy drop (default: 0.01).",
    )
    parser.add_argument(
        "--latency-rise-ratio",
        type=float,
        default=DEFAULT_LATENCY_RISE_RATIO,
        help="Regression threshold for latency rise ratio (default: 0.20).",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _build_arg_parser().parse_args(argv)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    thresholds = RegressionThresholds(
        pass_rate_drop=args.pass_rate_drop,
        domain_accuracy_drop=args.domain_accuracy_drop,
        latency_rise_ratio=args.latency_rise_ratio,
    )

    try:
        doc, regression, runs = aggregate(
            reports_dir=args.reports_dir,
            pattern=args.pattern,
            output=args.output,
            window=args.window,
            thresholds=thresholds,
        )
    except FileNotFoundError as exc:
        logger.error("%s", exc)
        return 2
    except Exception:  # noqa: BLE001 - surface unexpected failures with stack
        logger.exception("aggregation failed")
        return 2

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(doc, indent=2), encoding="utf-8")
    logger.info("wrote aggregate: %s (%d runs)", args.output, len(runs))

    if args.markdown is not None:
        md = render_markdown(runs, regression)
        args.markdown.parent.mkdir(parents=True, exist_ok=True)
        args.markdown.write_text(md, encoding="utf-8")
        logger.info("wrote markdown summary: %s", args.markdown)

    # Human-readable stdout summary — deliberately compact.
    if runs:
        latest = runs[-1]
        print(f"[aggregate] runs={len(runs)} "
              f"latest={latest.run_id} decision={latest.decision}")
        if regression.has_regression:
            print("[aggregate] REGRESSION:")
            for reason in regression.reasons:
                print(f"  - {reason}")
        else:
            print("[aggregate] no regressions vs previous run")
    else:
        print("[aggregate] no reports matched pattern")

    if args.fail_on_regression and regression.has_regression:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
