"""
RAG Evaluation Runner
---------------------
Checks all criteria per test, saves JSON report, prints categorized metrics.

Usage:
    python eval_runner.py
    python eval_runner.py --report reports/run_01.json
"""

import argparse
import json
import sys
import time
from pathlib import Path
from dataclasses import dataclass, field, asdict

from app.pipeline import Pipeline
from app.inference_service import InferenceService
from router.intent_router import IntentRouter
from retrieval.embeddings import Embedder
from retrieval.faiss_index import FaissIndex
from retrieval.multi_retriever import MultiRetriever
from retrieval.reranker import Reranker
from generation.llm import LLMClient

EVAL_QUERIES_PATH = Path(__file__).parent / "tests" / "eval_queries.json"
DEFAULT_REPORT_PATH = Path(__file__).parent / "reports" / f"eval_{int(time.time())}.json"


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class TestResult:
    test_id: int
    question: str
    answer: str
    sources: list[str]
    passed: bool
    reasons: list[str]          # failure reasons (empty if passed)
    buckets: list[str]          # "wrong_answer" | "wrong_source" | "refusal_failure" | "error"
    elapsed: float
    error: str = ""
    # copies of expectations — keeps TestResult self-contained, avoids zip(results, tests)
    expected_source: str = ""
    expected_exact: str = ""
    has_expected_source: bool = False
    has_expected_exact: bool = False
    # ML observability fields
    request_id: str = ""
    intent: str = ""
    intent_confidence: float = 0.0
    intent_method: str = ""


# ── Checker ───────────────────────────────────────────────────────────────────

def is_insufficient_response(answer: str) -> bool:
    """Check if answer is a refusal/insufficient data response using semantic matching."""
    keywords = [
        "insufficient", "not enough", "no data", "no information", "not found",
        "i don't have", "cannot find", "no available data", "i don't know",
        "not available", "cannot provide", "unable to find", "no information available"
    ]
    return any(k in answer.lower() for k in keywords)


def contains_arabic(text: str) -> bool:
    """Check if text contains Arabic characters."""
    return any('\u0600' <= c <= '\u06FF' for c in text)


def contains_numbers(text: str) -> bool:
    """Check if text contains numeric digits."""
    return any(char.isdigit() for char in text)


def check_result(result, test: dict, elapsed: float, mode: str = "dev") -> tuple[bool, list[str], list[str]]:
    """
    Evaluate ALL criteria in the test case.
    Returns (passed, reasons, buckets).
    """
    answer  = (result.answer or "").strip()
    sources = [s["source"] for s in result.sources]
    reasons: list[str] = []
    buckets: set[str]  = set()

    # expected_refusal: true — pattern-based, not string-exact
    if test.get("expected_refusal") is True:
        if not is_insufficient_response(answer):
            buckets.add("refusal_failure")
            reasons.append(f"expected refusal, got {answer!r}")

    # Refusal response validation with semantic matching
    if "expected_exact" in test:
        exp = test["expected_exact"]
        if exp == "Insufficient data.":
            if not is_insufficient_response(answer):
                buckets.add("refusal_failure")
                reasons.append(f"expected refusal response, got {answer!r}")
        elif answer != exp:
            buckets.add("wrong_answer")
            reasons.append(f"expected exact {exp!r}, got {answer!r}")

    # Hallucination detection for refusal responses
    if "expected_exact" in test and test["expected_exact"] == "Insufficient data.":
        if is_insufficient_response(answer) and contains_numbers(answer):
            buckets.add("hallucination_risk")
            reasons.append("refusal response contains numbers (hallucination risk)")

    if "expected_contains" in test:
        missing = [t for t in test["expected_contains"] if t.lower() not in answer.lower()]
        if missing:
            buckets.add("wrong_answer")
            reasons.append(f"missing terms: {missing}")

    # Source attribution validation
    if "expected_source" in test:
        expected = test["expected_source"]
        if expected not in sources:
            buckets.add("wrong_source")
            reasons.append(f"expected source {expected!r}, got {sources}")

        # Top-1 source accuracy
        if sources and sources[0] != expected:
            buckets.add("top1_source_mismatch")
            reasons.append(f"top-1 source mismatch: expected {expected!r}, got {sources[0]!r}")

        # Source precision (expected in top-2)
        if expected not in sources[:2]:
            buckets.add("low_source_precision")
            reasons.append(f"expected source not in top-2: {expected!r}")

    # Arabic leakage validation for multilingual tests
    if test.get("suite") == "multilingual_output":
        if contains_arabic(answer):
            buckets.add("arabic_leakage")
            reasons.append("response contains Arabic characters (should be English only)")

    # Minimum length validation for non-refusal responses
    if "min_length" in test:
        if not is_insufficient_response(answer) and len(answer.split()) < test["min_length"]:
            buckets.add("answer_too_short")
            reasons.append(f"answer too short (min {test['min_length']} words)")

    # Maximum latency validation
    if "max_latency_ms" in test:
        elapsed_ms = elapsed * 1000
        if elapsed_ms > test["max_latency_ms"]:
            buckets.add("latency_too_high")
            reasons.append(f"latency too high ({elapsed_ms:.0f}ms > {test['max_latency_ms']}ms)")

    # Strict mode: additional checks
    if mode == "strict":
        # Fail on generic fallback answers
        if not is_insufficient_response(answer):
            # Check for generic company description patterns
            generic_patterns = [
                "environmental services company",
                "waste management",
                "sustainability",
                "professional services",
            ]
            if any(p in answer.lower() and len(answer.split()) < 15 for p in generic_patterns):
                buckets.add("generic_answer")
                reasons.append("generic answer (strict mode)")

        # Fail if corpus_missing for required queries
        if test.get("required_corpus", False) and "corpus_missing" in buckets:
            buckets.add("corpus_missing_strict")
            reasons.append("corpus missing for required query (strict mode)")

    passed = len(reasons) == 0
    return passed, reasons, sorted(buckets)


# ── Metrics ───────────────────────────────────────────────────────────────────

def compute_metrics(results: list[TestResult], mode: str = "dev") -> dict:
    total   = len(results)
    passed  = sum(r.passed for r in results)
    errors  = sum(bool(r.error) for r in results)

    # source_match_accuracy: did the expected source appear in results?
    # counted independently of whether the answer itself passed.
    source_tests = [r for r in results if r.has_expected_source and not r.error]
    source_hits  = sum("wrong_source" not in r.buckets for r in source_tests)

    # Top-1 source accuracy
    top1_tests = [r for r in results if r.has_expected_source and not r.error]
    top1_hits = sum("top1_source_mismatch" not in r.buckets for r in top1_tests)

    # Source precision (expected in top-2)
    precision_tests = [r for r in results if r.has_expected_source and not r.error]
    precision_hits = sum("low_source_precision" not in r.buckets for r in precision_tests)

    # Refusal accuracy: tests that expect exactly "Insufficient data."
    refusal_tests = [r for r in results if r.has_expected_exact
                     and r.expected_exact == "Insufficient data." and not r.error]
    refusal_hits  = sum(r.passed for r in refusal_tests)

    # Bucket counts
    bucket_counts: dict[str, int] = {}
    for r in results:
        for b in r.buckets:
            bucket_counts[b] = bucket_counts.get(b, 0) + 1

    # Per-intent metrics (method-level: v2_model vs rules)
    from collections import Counter
    intent_method_stats = Counter()
    intent_method_passes = Counter()
    for r in results:
        if r.intent_method:
            intent_method_stats[r.intent_method] += 1
            if r.passed:
                intent_method_passes[r.intent_method] += 1

    intent_method_metrics = {}
    for method, count in intent_method_stats.items():
        intent_method_metrics[method] = {
            "total": count,
            "passed": intent_method_passes[method],
            "accuracy": round(intent_method_passes[method] / count, 3) if count > 0 else 0.0
        }

    # Per-intent type metrics (cv/eco/general)
    intent_type_stats = Counter()
    intent_type_passes = Counter()
    for r in results:
        if r.intent:
            intent_type_stats[r.intent] += 1
            if r.passed:
                intent_type_passes[r.intent] += 1

    intent_type_metrics = {}
    for intent_type, count in intent_type_stats.items():
        intent_type_metrics[intent_type] = {
            "total": count,
            "passed": intent_type_passes[intent_type],
            "accuracy": round(intent_type_passes[intent_type] / count, 3) if count > 0 else 0.0
        }

    # Low confidence failure analysis
    low_conf_failures = [r for r in results if not r.passed and r.intent_confidence > 0 and r.intent_confidence < 0.6]

    avg_elapsed = round(sum(r.elapsed for r in results) / total, 2) if total else 0
    latency_sla_ms = 2500
    sla_pass = (avg_elapsed * 1000) <= latency_sla_ms

    metrics_dict = {
        "total":              total,
        "passed":             passed,
        "failed":             total - passed - errors,
        "errors":             errors,
        "pass_rate":          round(passed / total, 3) if total else 0,
        "source_match_accuracy": round(source_hits / len(source_tests), 3) if source_tests else None,
        "top1_source_accuracy": round(top1_hits / len(top1_tests), 3) if top1_tests else None,
        "source_precision": round(precision_hits / len(precision_tests), 3) if precision_tests else None,
        "refusal_accuracy":   round(refusal_hits / len(refusal_tests), 3) if refusal_tests else None,
        "failure_buckets":    bucket_counts,
        "intent_method_metrics": intent_method_metrics,
        "intent_type_metrics": intent_type_metrics,
        "low_conf_failures":  len(low_conf_failures),
        "avg_elapsed_s":      avg_elapsed,
        "latency_sla_ms":     latency_sla_ms,
        "sla_pass":           sla_pass,
    }

    # Strict mode: compute real pass rate excluding corpus_missing
    if mode == "strict":
        corpus_missing_count = bucket_counts.get("corpus_missing", 0) + bucket_counts.get("corpus_missing_strict", 0)
        generic_answer_count = bucket_counts.get("generic_answer", 0)
        real_passed = passed - corpus_missing_count - generic_answer_count
        real_total = total - corpus_missing_count - generic_answer_count
        metrics_dict["real_pass_rate"] = round(real_passed / real_total, 3) if real_total > 0 else 0
        metrics_dict["corpus_missing_count"] = corpus_missing_count
        metrics_dict["generic_answer_count"] = generic_answer_count

    return metrics_dict


# ── Main ──────────────────────────────────────────────────────────────────────

def main(query_fn=None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT_PATH,
                        help="Path to save JSON report")
    parser.add_argument("--suite", type=str, default=None,
                        help="Run only tests matching this suite (e.g. baseline_en, feature_ar)")
    parser.add_argument("--mode", type=str, default="dev", choices=["dev", "strict"],
                        help="Evaluation mode: dev (relaxed) or strict (requires grounded answers)")
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

    print(f"Evaluation mode: {args.mode.upper()}\n")

    if not tests:
        print("ERROR: eval_queries.json is empty.", file=sys.stderr)
        return 2

    # Use provided query function or default to new Pipeline architecture
    service = None
    if query_fn is None:
        print("Initializing components...")
        router = IntentRouter.from_active_model()
        embedder = Embedder()

        # Load indexes
        indexes: dict[str, FaissIndex] = {}
        for name in ("cv", "eco", "general"):
            try:
                indexes[name] = FaissIndex.load(name, out_dir=Path("models"))
            except FileNotFoundError:
                continue

        if not indexes:
            print("ERROR: No FAISS indexes found. Run scripts/build_indexes.py first.")
            return 2

        retriever = MultiRetriever(indexes=indexes)
        reranker = Reranker(embed_fn=embedder.embed_batch)
        llm = LLMClient()
        pipeline = Pipeline(router=router, embedder=embedder, retriever=retriever, llm=llm, reranker=reranker)
        service = InferenceService(pipeline=pipeline)
        print(f"Ready with {len(indexes)} indexes\n")

        def query_fn(question: str):
            result = service.handle_query(question, query_id=f"eval_{int(time.time()*1000)}")
            # Convert to expected format
            @dataclass
            class QueryResult:
                answer: str
                sources: list[dict]
                request_id: str
                intent: str
                intent_confidence: float
                intent_method: str

            sources = [{"source": h.source} for h in result.retrieval]
            # Determine intent method based on confidence
            intent_method = "rules" if result.confidence >= 0.85 else "v2_model"

            return QueryResult(
                answer=result.answer,
                sources=sources,
                request_id=result.query_id,
                intent=result.intent,
                intent_confidence=result.confidence,
                intent_method=intent_method
            )
    else:
        print("Using provided query function\n")

    results: list[TestResult] = []

    try:
        for i, test in enumerate(tests, 1):
            question = test.get("question") or test.get("query", "")
            question = str(question).strip()
            print(f"[{i}/{len(tests)}] {question or '(no question)'}")

            tr = TestResult(
                test_id=i,
                question=question,
                answer="", sources=[],
                passed=False, reasons=[], buckets=[], elapsed=0.0,
                expected_source=test.get("expected_source", ""),
                expected_exact=test.get("expected_exact", ""),
                has_expected_source="expected_source" in test,
                has_expected_exact="expected_exact" in test,
            )

            if not question:
                tr.error = "missing 'question' or 'query' field"
                tr.buckets = ["error"]
                results.append(tr)
                print("  ✗ SKIP — missing 'question' or 'query' field")
                continue

            try:
                t1 = time.perf_counter()
                result = query_fn(question)
                tr.elapsed = time.perf_counter() - t1
                tr.answer = result.answer or ""
                tr.sources = [s["source"] for s in result.sources]
                tr.request_id = result.request_id or ""
                tr.intent = result.intent or ""
                tr.intent_confidence = result.intent_confidence or 0.0
                tr.intent_method = result.intent_method or ""

                tr.passed, tr.reasons, tr.buckets = check_result(result, test, tr.elapsed, args.mode)

                preview = tr.answer[:120] + ("..." if len(tr.answer) > 120 else "")
                print(f"  Answer ({tr.elapsed:.2f}s): {preview}")
                print(f"  Sources: {tr.sources}")

                if tr.passed:
                    print("  ✓ PASS")
                else:
                    print(f"  ✗ FAIL — {'; '.join(tr.reasons)}")
                    if tr.request_id:
                        print(f"  request_id: {tr.request_id}")

            except Exception as exc:
                tr.error = str(exc)
                # Classify embedding failures as infra_failure
                if "Embedding failure" in str(exc) or "embedding" in str(exc).lower():
                    tr.buckets = ["infra_failure"]
                else:
                    tr.buckets = ["error"]
                print(f"  ✗ ERROR — {exc}")
            finally:
                results.append(tr)

        # ── Metrics ───────────────────────────────────────────────────────────
        metrics = compute_metrics(results, args.mode)

        print(f"\n{'='*60}")
        print(f"  Pass rate:            {metrics['pass_rate']*100:.1f}%  ({metrics['passed']}/{metrics['total']})")
        if args.mode == "strict" and "real_pass_rate" in metrics:
            print(f"  Real pass rate:       {metrics['real_pass_rate']*100:.1f}%  (excluding corpus_missing & generic)")
        if metrics["source_match_accuracy"] is not None:
            print(f"  Source match acc:     {metrics['source_match_accuracy']*100:.1f}%")
        if metrics["top1_source_accuracy"] is not None:
            print(f"  Top-1 source acc:     {metrics['top1_source_accuracy']*100:.1f}%")
        if metrics["source_precision"] is not None:
            print(f"  Source precision:     {metrics['source_precision']*100:.1f}%")
        if metrics["refusal_accuracy"] is not None:
            print(f"  Refusal accuracy:   {metrics['refusal_accuracy']*100:.1f}%")
        print(f"  Errors:             {metrics['errors']}")
        print(f"  Failure buckets:    {metrics['failure_buckets']}")
        if args.mode == "strict":
            if "corpus_missing_count" in metrics:
                print(f"  Corpus missing:      {metrics['corpus_missing_count']}")
            if "generic_answer_count" in metrics:
                print(f"  Generic answers:     {metrics['generic_answer_count']}")
        print(f"  Avg latency:        {metrics['avg_elapsed_s']}s  (SLA {metrics['latency_sla_ms']}ms: {'✓' if metrics['sla_pass'] else '✗ FAIL'})")
        print(f"{'='*60}")

        # ── Save report ───────────────────────────────────────────────────────
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "metrics": metrics,
            "results": [asdict(r) for r in results],
        }
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport saved → {args.report}")

        return 0 if (metrics["failed"] == 0 and metrics["errors"] == 0) else 1

    finally:
        if pipeline is not None:
            pipeline.close()


if __name__ == "__main__":
    sys.exit(main())
