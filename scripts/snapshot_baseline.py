"""Capture a named baseline snapshot of eval + drift + alerts state.

Runs the three measurement passes the project uses to quantify system
quality and writes every artifact under `reports/<label>/` so before
vs. after comparisons are reproducible. Nothing else: no analysis, no
diffs, no automation. Use twice — once before ingestion, once after —
and diff the outputs.

Usage:
    python scripts/snapshot_baseline.py --label before
    # ... run ingestion + reindex ...
    python scripts/snapshot_baseline.py --label after
"""

from __future__ import annotations

import argparse
import logging
import subprocess
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parent.parent

logger = logging.getLogger(__name__)


def _run(cmd: list[str], *, stdout_path: Path | None = None) -> int:
    logger.info("$ %s", " ".join(cmd))
    if stdout_path is not None:
        stdout_path.parent.mkdir(parents=True, exist_ok=True)
        with stdout_path.open("w", encoding="utf-8") as fh:
            result = subprocess.run(cmd, stdout=fh, stderr=subprocess.STDOUT, cwd=_REPO_ROOT)
    else:
        result = subprocess.run(cmd, cwd=_REPO_ROOT)
    if result.returncode != 0:
        logger.warning("Command exited with code %d: %s", result.returncode, " ".join(cmd))
    return result.returncode


def snapshot(label: str, *, reports_dir: Path, min_queries: int, min_misses: int) -> int:
    out_dir = reports_dir / label
    out_dir.mkdir(parents=True, exist_ok=True)

    eval_report = out_dir / "eval_strict.json"
    eval_stdout = out_dir / "eval_strict.txt"
    drift_report = out_dir / "drift.json"
    alerts_report = out_dir / "alerts.json"

    python = sys.executable

    rc_eval = _run(
        [python, "eval_runner.py", "--mode", "strict", "--report", str(eval_report)],
        stdout_path=eval_stdout,
    )
    rc_drift = _run([
        python, "-m", "analysis.drift_detector",
        "--min-queries", str(min_queries),
        "--min-misses", str(min_misses),
        "--output", str(drift_report),
    ])
    rc_alerts = _run([
        python, "-m", "analysis.alerts",
        "--min-queries", str(min_queries),
        "--min-misses", str(min_misses),
        "--output", str(alerts_report),
    ])

    logger.info("Snapshot '%s' written to %s", label, out_dir)
    logger.info(
        "Exit codes: eval=%d drift=%d alerts=%d",
        rc_eval,
        rc_drift,
        rc_alerts,
    )
    return rc_eval or rc_drift or rc_alerts


def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Snapshot eval + drift + alerts under reports/<label>/.")
    parser.add_argument(
        "--label",
        required=True,
        help="Snapshot name; outputs land under reports/<label>/.",
    )
    parser.add_argument(
        "--reports-dir",
        type=Path,
        default=_REPO_ROOT / "reports",
        help="Root directory for snapshot output.",
    )
    parser.add_argument("--min-queries", type=int, default=5)
    parser.add_argument("--min-misses", type=int, default=3)
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return snapshot(
        args.label,
        reports_dir=args.reports_dir,
        min_queries=args.min_queries,
        min_misses=args.min_misses,
    )


if __name__ == "__main__":
    sys.exit(_main())
