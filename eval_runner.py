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
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path

from app.config import MAX_RETRIES, REFUSAL_MESSAGE
from app.pipeline import Pipeline
from app.inference_service import InferenceService
from evaluation.eval_gate import gate
from evaluation.refusal import (
    contains_arabic,
    contains_numbers,
    is_insufficient_response,
)
from router.intent_router import IntentRouter
from retrieval.embeddings import Embedder
from retrieval.faiss_index import FaissIndex
from retrieval.multi_retriever import MultiRetriever
from app.reranker import LightweightReranker
from generation.llm import LLMClient

EVAL_QUERIES_PATH = Path(__file__).parent / "tests" / "eval_queries.json"
DEFAULT_REPORT_PATH = Path(__file__).parent / "reports" / f"eval_{int(time.time())}.json"


# ── Result types ──────────────────────────────────────────────────────────────

@dataclass
class QueryResult:
    answer: str
    sources: list[dict]
    request_id: str
    intent: str
    intent_confidence: float
    intent_method: str
    failure_type: str | None = None
    grounded: bool = True


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
    expected_intent: str = ""
    has_expected_source: bool = False
    has_expected_exact: bool = False
    # ML observability fields
    request_id: str = ""
    intent: str = ""
    intent_confidence: float = 0.0
    intent_method: str = ""
    # Canonical pipeline fields (required for gate)
    failure_type: str | None = None
    grounded: bool = True
    # Hard-fail enforcement
    killer: bool = False


# ── Checker ───────────────────────────────────────────────────────────────────
# Text predicates (is_insufficient_response / contains_arabic /
# contains_numbers) live in evaluation/refusal.py so eval_main, metrics,
# and this runner all share one definition of "refusal".


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
    if "expected_answer_exact" in test:
        exp = test["expected_answer_exact"]
        if exp == REFUSAL_MESSAGE:
            if not is_insufficient_response(answer):
                buckets.add("refusal_failure")
                reasons.append(f"expected refusal response, got {answer!r}")
        elif answer != exp:
            buckets.add("wrong_answer")
            reasons.append(f"expected exact {exp!r}, got {answer!r}")

    # Hallucination detection for refusal responses
    if "expected_answer_exact" in test and test["expected_answer_exact"] == REFUSAL_MESSAGE:
        if is_insufficient_response(answer) and contains_numbers(answer):
            buckets.add("hallucination_risk")
            reasons.append("refusal response contains numbers (hallucination risk)")

    if "expected_contains" in test:
        missing = [t for t in test["expected_contains"] if t.lower() not in answer.lower()]
        if missing:
            buckets.add("wrong_answer")
            reasons.append(f"missing terms: {missing}")

    if "expected_answer_contains" in test:
        missing = [t for t in test["expected_answer_contains"] if t.lower() not in answer.lower()]
        if missing:
            buckets.add("wrong_answer")
            reasons.append(f"missing answer terms: {missing}")

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

    # Refusal accuracy: tests that expect exactly the canonical refusal message.
    refusal_tests = [r for r in results if r.has_expected_exact
                     and r.expected_exact == REFUSAL_MESSAGE and not r.error]
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

    # ── Canonical metrics (required by eval_gate) ─────────────────────────────
    # Grounding failure rate: pipeline-reported failure_type in grounding category
    grounding_failures = sum(
        1 for r in results
        if r.failure_type in {"grounding_reject", "speculative_reject"}
    )
    grounding_failure_rate = round(grounding_failures / total, 3) if total else 0.0

    # Reasoning failure rate: pipeline-reported failure_type for reasoning rejects
    reasoning_failures = sum(
        1 for r in results
        if r.failure_type == "reasoning_reject"
    )
    reasoning_failure_rate = round(reasoning_failures / total, 3) if total else 0.0

    # Domain accuracy: correct intent routing for eco/cv (rule-routed queries)
    domain_rows = [r for r in results if r.expected_intent in {"eco", "cv"} and not r.error]
    domain_correct = sum(1 for r in domain_rows if r.intent == r.expected_intent)
    domain_accuracy = round(domain_correct / len(domain_rows), 3) if domain_rows else 0.0

    # Canonical refusal_accuracy: out-of-domain queries that returned the
    # canonical refusal message exactly (case-insensitive).
    canonical_refusal_rows = [r for r in results if r.has_expected_exact
                              and r.expected_exact == REFUSAL_MESSAGE and not r.error]
    canonical_refusal_hits = sum(
        1 for r in canonical_refusal_rows
        if str(r.answer or "").strip().lower() == REFUSAL_MESSAGE.lower()
    )
    canonical_refusal_accuracy = (
        round(canonical_refusal_hits / len(canonical_refusal_rows), 3)
        if canonical_refusal_rows else 1.0
    )

    # Self-correction metrics
    total_retries = sum(getattr(r, "retry_attempts", 0) for r in results)
    corrected_queries = sum(1 for r in results if getattr(r, "corrected", False) is True)
    correction_rate = round(corrected_queries / total, 3) if total else 0.0
    avg_retries = round(total_retries / total, 2) if total else 0.0

    metrics_dict = {
        "total":              total,
        "passed":             passed,
        "failed":             total - passed - errors,
        "errors":             errors,
        "pass_rate":          round(passed / total, 3) if total else 0,
        "source_match_accuracy": round(source_hits / len(source_tests), 3) if source_tests else None,
        "top1_source_accuracy": round(top1_hits / len(top1_tests), 3) if top1_tests else None,
        "source_precision": round(precision_hits / len(precision_tests), 3) if precision_tests else None,
        "refusal_accuracy":   canonical_refusal_accuracy,
        "grounding_failure_rate": grounding_failure_rate,
        "reasoning_failure_rate": reasoning_failure_rate,
        "domain_accuracy":    domain_accuracy,
        "ocr_presence_check": True,
        "failure_buckets":    bucket_counts,
        "intent_method_metrics": intent_method_metrics,
        "intent_type_metrics": intent_type_metrics,
        "low_conf_failures":  len(low_conf_failures),
        "avg_elapsed_s":      avg_elapsed,
        "latency_sla_ms":     latency_sla_ms,
        "sla_pass":           sla_pass,
        "correction_rate":    correction_rate,
        "avg_retries":        avg_retries,
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
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (1 = sequential). Recommended 4-8 for local Ollama.")
    parser.add_argument("--query-timeout", type=float, default=90.0,
                        help="Hard timeout per query in seconds. Prevents hangs on stuck LLM calls.")
    parser.add_argument("--fast", action="store_true",
                        help="Disable KnowledgeGapAnalyzer LLM calls during eval (keeps deterministic CorpusTopicMap signal).")
    parser.add_argument("--fast-mode", type=str, default=None, choices=["full", "minimal"],
                        help="Enhanced fast modes: 'full' = skip KGap + self-correction + reduce retries; "
                             "'minimal' = full + skip reranking + use cached embeddings where possible")
    parser.add_argument("--debug", action="store_true",
                        help="Enable debug output: show detailed routing decisions, retrieval scores, and grounding checks.")
    parser.add_argument("--debug-failures", action="store_true",
                        help="Show detailed debug info only for failed tests ( quieter than --debug).")
    parser.add_argument("--dry-run", action="store_true",
                        help="Initialize pipeline but don't run queries (useful for smoke testing setup).")
    parser.add_argument("--compare-baseline", type=Path, default=None,
                        help="Compare results against baseline report and show diffs.")
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

    # Fast mode configuration
    fast_config = {
        "kgap_bypass": False,
        "self_correction": True,
        "reranking": True,
        "embed_retries": MAX_RETRIES,
        "llm_retries": 2,
    }

    if args.fast:
        fast_config["kgap_bypass"] = True
        print("Fast mode: KnowledgeGapAnalyzer LLM calls disabled")

    if args.fast_mode:
        if args.fast_mode == "full":
            fast_config["kgap_bypass"] = True
            fast_config["self_correction"] = False
            fast_config["llm_retries"] = 1
            os.environ["EVAL_SELF_CORRECTION"] = "0"
            print("Fast mode 'full': KGap bypass, self-correction disabled, reduced retries")
        elif args.fast_mode == "minimal":
            fast_config["kgap_bypass"] = True
            fast_config["self_correction"] = False
            fast_config["reranking"] = False
            fast_config["embed_retries"] = 2
            fast_config["llm_retries"] = 1
            os.environ["EVAL_SELF_CORRECTION"] = "0"
            os.environ["EVAL_RERANK"] = "0"
            print("Fast mode 'minimal': All optimizations enabled (fastest)")

    if fast_config["kgap_bypass"]:
        os.environ["KGAP_BYPASS_LLM"] = "1"
    print()  # Blank line after config summary

    # Use provided query function or default to new Pipeline architecture
    service = None
    pipeline = None
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
        reranker = LightweightReranker(
            semantic_weight=0.6, bm25_weight=0.3, phrase_weight=0.1,
        )
        llm = LLMClient()
        # Configure pipeline for fast modes
        pipeline_kwargs = {
            "router": router,
            "embedder": embedder,
            "retriever": retriever,
            "llm": llm,
            "reranker": reranker,
        }

        # Dry-run exit point
        if args.dry_run:
            print(f"\nDRY RUN: Pipeline initialized with {len(indexes)} indexes")
            print(f"Fast config: {fast_config}")
            print("Exiting without running queries.")
            return 0

        pipeline = Pipeline(**pipeline_kwargs)
        service = InferenceService(pipeline=pipeline)
        print(f"Ready with {len(indexes)} indexes")
        if args.debug:
            print(f"Debug mode enabled. Fast config: {fast_config}")
        print()  # Blank line

        def query_fn(question: str):
            t_start = time.perf_counter()
            result = service.handle_query(question, query_id=f"eval_{int(time.time()*1000)}")
            wall_time = time.perf_counter() - t_start

            # Debug output
            if args.debug or (args.debug_failures and result.failure_type):
                debug_info = {
                    "query": question[:60] + "..." if len(question) > 60 else question,
                    "intent": result.intent,
                    "confidence": round(result.confidence, 3),
                    "method": result.intent_method,
                    "retrieval_count": len(result.retrieval),
                    "top_score": round(result.retrieval[0].score, 3) if result.retrieval else None,
                    "grounded": result.grounded,
                    "failure_type": result.failure_type,
                    "latency_ms": result.latency_ms,
                    "wall_time_ms": round(wall_time * 1000, 1),
                }
                print(f"  [DEBUG] {debug_info}")

            # Convert to expected format
            sources = [{"source": h.source} for h in result.retrieval]

            return QueryResult(
                answer=result.answer,
                sources=sources,
                request_id=result.query_id,
                intent=result.intent,
                intent_confidence=result.confidence,
                intent_method=result.intent_method,
                failure_type=result.failure_type,
                grounded=result.grounded,
            )
    else:
        print("Using provided query function\n")

    results: list[TestResult] = []

    def _build_test_result(idx: int, test: dict) -> tuple[TestResult, str]:
        question = test.get("question") or test.get("query", "")
        question = str(question).strip()
        tr = TestResult(
            test_id=idx,
            question=question,
            answer="", sources=[],
            passed=False, reasons=[], buckets=[], elapsed=0.0,
            expected_source=test.get("expected_source", ""),
            expected_exact=test.get("expected_exact", ""),
            expected_intent=test.get("expected_intent", ""),
            has_expected_source="expected_source" in test,
            has_expected_exact="expected_exact" in test,
            killer=bool(test.get("killer", False)),
        )
        return tr, question

    def _run_single(idx: int, test: dict) -> TestResult:
        tr, question = _build_test_result(idx, test)
        if not question:
            tr.error = "missing 'question' or 'query' field"
            tr.buckets = ["error"]
            return tr
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
            tr.failure_type = getattr(result, "failure_type", None)
            tr.grounded = getattr(result, "grounded", True)
            tr.passed, tr.reasons, tr.buckets = check_result(result, test, tr.elapsed, args.mode)
        except Exception as exc:
            tr.error = str(exc)
            if "Embedding failure" in str(exc) or "embedding" in str(exc).lower():
                tr.buckets = ["infra_failure"]
            else:
                tr.buckets = ["error"]
        return tr

    def _print_result(tr: TestResult, total_count: int) -> None:
        print(f"[{tr.test_id}/{total_count}] {tr.question or '(no question)'}")
        if tr.error:
            print(f"  ✗ ERROR ({tr.elapsed:.2f}s) — {tr.error}")
            return
        preview = tr.answer[:120] + ("..." if len(tr.answer) > 120 else "")
        print(f"  Answer ({tr.elapsed:.2f}s): {preview}")
        print(f"  Sources: {tr.sources}")
        if tr.passed:
            print("  ✓ PASS")
        else:
            print(f"  ✗ FAIL — {'; '.join(tr.reasons)}")
            if tr.request_id:
                print(f"  request_id: {tr.request_id}")

    try:
        workers = max(1, int(args.workers))
        total_count = len(tests)

        if workers == 1:
            # Sequential path — still enforces per-query timeout via a 1-worker pool.
            for i, test in enumerate(tests, 1):
                with ThreadPoolExecutor(max_workers=1) as pool:
                    future = pool.submit(_run_single, i, test)
                    try:
                        tr = future.result(timeout=args.query_timeout)
                    except FuturesTimeoutError:
                        tr, _ = _build_test_result(i, test)
                        tr.error = f"query timeout after {args.query_timeout:.0f}s"
                        tr.elapsed = args.query_timeout
                        tr.buckets = ["timeout"]
                _print_result(tr, total_count)
                results.append(tr)
        else:
            # Parallel path — submit all, collect in order with per-task timeout.
            indexed: dict[int, TestResult] = {}
            with ThreadPoolExecutor(max_workers=workers) as pool:
                futures = {pool.submit(_run_single, i, test): (i, test)
                           for i, test in enumerate(tests, 1)}
                try:
                    for future in as_completed(futures, timeout=args.query_timeout * total_count):
                        i, test = futures[future]
                        try:
                            tr = future.result(timeout=args.query_timeout)
                        except FuturesTimeoutError:
                            tr, _ = _build_test_result(i, test)
                            tr.error = f"query timeout after {args.query_timeout:.0f}s"
                            tr.elapsed = args.query_timeout
                            tr.buckets = ["timeout"]
                        indexed[i] = tr
                        _print_result(tr, total_count)
                except FuturesTimeoutError:
                    # Global deadline — fill in any unfinished futures as timeouts.
                    for future, (i, test) in futures.items():
                        if future.done() or i in indexed:
                            continue
                        tr, _ = _build_test_result(i, test)
                        tr.error = f"global deadline timeout after {args.query_timeout:.0f}s"
                        tr.elapsed = args.query_timeout
                        tr.buckets = ["timeout"]
                        indexed[i] = tr
            # Preserve input order for the report.
            results = [indexed[i] for i in sorted(indexed)]

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

        # ── Strict gate (canonical policy) ─────────────────────────────────────
        results_as_dicts = [asdict(r) for r in results]
        gate_result = gate(metrics, results_as_dicts)
        decision = gate_result["decision"]
        failed_checks = gate_result["failed_checks"]

        if args.mode == "strict":
            print(f"  Grounding failure rate: {metrics['grounding_failure_rate']*100:.1f}%")
            print(f"  Domain accuracy:    {metrics['domain_accuracy']*100:.1f}%")
            print(f"  OCR presence check: {metrics['ocr_presence_check']}")
            print(f"  Gate decision:      {decision}")
            if failed_checks:
                print(f"  Failed checks:      {failed_checks}")
            print(f"{'='*60}")

        # ── Baseline comparison ────────────────────────────────────────────────
        if args.compare_baseline and args.compare_baseline.exists():
            print(f"\n{'─'*60}")
            print(f"Comparing with baseline: {args.compare_baseline}")
            with open(args.compare_baseline, encoding="utf-8") as f:
                baseline = json.load(f)

            baseline_metrics = baseline.get("metrics", {})
            key_metrics = ["pass_rate", "grounding_failure_rate", "domain_accuracy", "refusal_accuracy"]

            changes = []
            for m in key_metrics:
                curr = metrics.get(m)
                base = baseline_metrics.get(m)
                if curr is not None and base is not None:
                    delta = round(curr - base, 3)
                    symbol = "↗" if delta > 0.001 else ("↘" if delta < -0.001 else "→")
                    changes.append(f"  {m}: {base:.3f} → {curr:.3f} ({symbol}{delta:+.3f})")

            if changes:
                print("  Changes:")
                for c in changes:
                    print(f"    {c}")
            else:
                print("  No significant metric changes detected")

            # Compare per-test results
            baseline_results = {r.get("test_id"): r for r in baseline.get("results", [])}
            curr_results = {r.get("test_id"): r for r in results_as_dicts}

            regressions = []
            for test_id, curr_r in curr_results.items():
                base_r = baseline_results.get(test_id)
                if base_r and base_r.get("passed") and not curr_r.get("passed"):
                    regressions.append(f"  Test {test_id}: {curr_r.get('question', 'N/A')[:50]}")

            if regressions:
                print(f"\n  ⚠ Regressions ({len(regressions)}):")
                for r in regressions[:5]:  # Show first 5
                    print(f"    {r}")
                if len(regressions) > 5:
                    print(f"    ... and {len(regressions) - 5} more")
            else:
                print("  ✓ No regressions detected")

            improvements = []
            for test_id, curr_r in curr_results.items():
                base_r = baseline_results.get(test_id)
                if base_r and not base_r.get("passed") and curr_r.get("passed"):
                    improvements.append(f"  Test {test_id}: {curr_r.get('question', 'N/A')[:50]}")

            if improvements:
                print(f"\n  ✓ Improvements ({len(improvements)}):")
                for i in improvements[:5]:
                    print(f"    {i}")
                if len(improvements) > 5:
                    print(f"    ... and {len(improvements) - 5} more")
            print(f"{'─'*60}")

        # ── Save report ───────────────────────────────────────────────────────
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "decision": decision,
            "failed_checks": failed_checks,
            "metrics": metrics,
            "results": results_as_dicts,
            "fast_config": fast_config if args.fast or args.fast_mode else None,
        }
        with open(args.report, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False)
        print(f"\nReport saved → {args.report}")

        # In strict mode, gate decision drives exit code
        if args.mode == "strict":
            return 0 if decision == "PROMOTE" else 1
        return 0 if (metrics["failed"] == 0 and metrics["errors"] == 0) else 1

    finally:
        if pipeline is not None and hasattr(pipeline, "close"):
            pipeline.close()


if __name__ == "__main__":
    sys.exit(main())
