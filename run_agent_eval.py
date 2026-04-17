from __future__ import annotations

import argparse
import importlib.util
import json
import logging
import sys
import time
from dataclasses import asdict
from pathlib import Path

# ---- Paths ----
OPENCLAW_PATH = Path(r"C:\openclaw")
ASSISTANT_PATH = Path(r"D:\AI\assistant")

sys.path.insert(0, str(OPENCLAW_PATH))
sys.path.insert(0, str(ASSISTANT_PATH))

# ---- Core imports ----
from router import route_task  # type: ignore
from app.rag_service import get_rag_service  # type: ignore
from eval_runner import (  # type: ignore
    TestResult,
    check_result,
    compute_metrics,
    EVAL_QUERIES_PATH,
    DEFAULT_REPORT_PATH,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger(__name__)


def load_module(module_name: str, file_path: Path):
    spec = importlib.util.spec_from_file_location(module_name, str(file_path))
    if spec is None or spec.loader is None:
        raise ImportError(f"Could not load module {module_name} from {file_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


# Load agent tool modules with unique names to avoid "tools" import collisions
research_tools = load_module(
    "openclaw_research_tools",
    OPENCLAW_PATH / "agents" / "research" / "tools.py",
)
analyst_tools = load_module(
    "openclaw_analyst_tools",
    OPENCLAW_PATH / "agents" / "analyst" / "tools.py",
)


class RagResponse:
    """
    Contract expected by eval_runner.check_result():
      - answer: str
      - sources: list[dict] with {"source": str, "chunk_id": str}
    """

    def __init__(self, answer: str, sources):
        self.answer = answer or ""
        self.sources = [
            s if isinstance(s, dict) else {"source": str(s), "chunk_id": ""}
            for s in (sources or [])
        ]


def normalize_agent_result(result: dict) -> tuple[str, list[dict]]:
    answer = result.get("answer") or result.get("analysis") or ""
    raw_sources = result.get("sources", []) or []

    sources: list[dict] = []
    for i, s in enumerate(raw_sources):
        if isinstance(s, dict):
            sources.append(
                {
                    "source": str(s.get("source", "")),
                    "chunk_id": str(s.get("chunk_id", "")),
                }
            )
        else:
            sources.append({"source": str(s), "chunk_id": f"agent_{i}"})

    return answer, sources


def agent_query(question: str) -> RagResponse:
    try:
        agent = route_task(question)

        if agent == "research":
            result = research_tools.research_query(question)
            answer, sources = normalize_agent_result(result)
            return RagResponse(answer, sources)

        if agent == "analyst":
            result = analyst_tools.analyze_with_rag(question)
            answer, sources = normalize_agent_result(result)
            return RagResponse(answer, sources)

        # Fallback: direct RAG service
        response = get_rag_service().query(question)
        return RagResponse(response.answer, response.sources)

    except Exception as e:
        logger.error("agent_query failed for %r: %s", question, e)
        return RagResponse("Insufficient data.", [])


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT_PATH.parent / "agent_eval_proper.json",
        help="Path to save JSON report",
    )
    parser.add_argument(
        "--suite",
        type=str,
        default=None,
        help="Run only tests matching this suite",
    )
    args = parser.parse_args()

    if not EVAL_QUERIES_PATH.exists():
        print(f"ERROR: {EVAL_QUERIES_PATH} not found.", file=sys.stderr)
        return 2

    with open(EVAL_QUERIES_PATH, encoding="utf-8") as f:
        tests: list[dict] = json.load(f)

    if args.suite:
        tests = [t for t in tests if t.get("suite") == args.suite]
        if not tests:
            print(f"ERROR: no tests found for suite={args.suite!r}", file=sys.stderr)
            return 2
        print(f"Suite filter: {args.suite!r} → {len(tests)} tests\n")

    if not tests:
        print("ERROR: eval_queries.json is empty.", file=sys.stderr)
        return 2

    print("Using provided query function\n")

    results: list[TestResult] = []

    for i, test in enumerate(tests, 1):
        question = test.get("question", "").strip()
        print(f"[{i}/{len(tests)}] {question or '(no question)'}")

        tr = TestResult(
            test_id=i,
            question=question,
            answer="",
            sources=[],
            passed=False,
            reasons=[],
            buckets=[],
            elapsed=0.0,
            expected_source=test.get("expected_source", ""),
            expected_exact=test.get("expected_exact", ""),
            has_expected_source="expected_source" in test,
            has_expected_exact="expected_exact" in test,
        )

        if not question:
            tr.error = "missing 'question' field"
            tr.buckets = ["error"]
            results.append(tr)
            print("  ✗ SKIP — missing 'question' field")
            continue

        try:
            t1 = time.perf_counter()
            result = agent_query(question)
            tr.elapsed = time.perf_counter() - t1
            tr.answer = result.answer or ""
            tr.sources = [s["source"] for s in result.sources]

            tr.passed, tr.reasons, tr.buckets = check_result(result, test, tr.elapsed)

            preview = tr.answer[:120] + ("..." if len(tr.answer) > 120 else "")
            print(f"  Answer ({tr.elapsed:.2f}s): {preview}")
            print(f"  Sources: {result.sources}")

            if tr.passed:
                print("  ✓ PASS")
            else:
                print(f"  ✗ FAIL — {'; '.join(tr.reasons)}")

        except Exception as e:
            tr.error = str(e)
            tr.buckets = ["error"]
            print(f"  ✗ ERROR — {e}")

        results.append(tr)

    metrics = compute_metrics(results)

    print(f"\n{'=' * 60}")
    print(f"  Pass rate:            {metrics['pass_rate']*100:.1f}%  ({metrics['passed']}/{metrics['total']})")
    if metrics["source_match_accuracy"] is not None:
        print(f"  Source match acc:     {metrics['source_match_accuracy']*100:.1f}%")
    if metrics.get("refusal_accuracy") is not None:
        print(f"  Refusal accuracy:     {metrics['refusal_accuracy']*100:.1f}%")
    print(f"  Errors:               {metrics['errors']}")
    print(f"  Failure buckets:      {metrics['failure_buckets']}")
    print(f"  Avg latency:          {metrics['avg_elapsed_s']}s")
    print(f"{'=' * 60}")

    args.report.parent.mkdir(parents=True, exist_ok=True)
    report = {
        "metrics": metrics,
        "results": [asdict(r) for r in results],
    }
    with open(args.report, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    print(f"\nReport saved → {args.report}")

    # Enforce 95% pass rate gate
    MIN_PASS_RATE = 0.95
    pass_rate = metrics['pass_rate']

    print(f"\n{'=' * 60}")
    print(f"QUALITY GATE CHECK")
    print(f"{'=' * 60}")
    print(f"Required pass rate: {MIN_PASS_RATE * 100:.1f}%")
    print(f"Actual pass rate:   {pass_rate * 100:.1f}%")

    if pass_rate >= MIN_PASS_RATE:
        print(f"✅ QUALITY GATE PASSED")
        return 0 if (metrics["failed"] == 0 and metrics["errors"] == 0) else 1
    else:
        print(f"❌ QUALITY GATE FAILED")
        print(f"\nTo proceed:")
        print(f"1. Fix the failing cases above")
        print(f"2. Re-run: python run_agent_eval.py")
        print(f"\nBuild FAILED due to insufficient pass rate")
        return 1


if __name__ == "__main__":
    sys.exit(main())
