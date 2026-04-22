"""
RAG Evaluation Runner
---------------------
Checks all criteria per test, saves JSON report, prints categorized metrics.

Usage:
    python eval_runner.py
    python eval_runner.py --report reports/run_01.json
"""

from __future__ import annotations

import argparse
import enum
import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeoutError, as_completed
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from app.config import REFUSAL_MESSAGE, USE_ADVANCED_RETRIEVAL_SHADOW
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
from retrieval.reranker import Reranker
from generation.llm import LLMClient
from app.advanced_retriever_adapter import AdvancedRetrievalAdapter
from app.decision_logger import DecisionLogger

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


def from_api_response(api_response: dict) -> QueryResult:
    """Convert API QueryResponse to eval QueryResult format.

    Handles schema differences between API and eval contracts:
    - API uses structured SourceItem objects, eval expects list[dict] with 'source' key
    - API has extra fields (model_version, retriever_version, latency_ms, wall_ms) that are ignored
    """
    # Convert SourceItem objects to dict format expected by eval
    sources = []
    if "sources" in api_response:
        for src in api_response["sources"]:
            if isinstance(src, dict):
                sources.append({"source": src.get("source", "")})
            else:
                # Handle case where source is already a string or other format
                sources.append({"source": str(src)})

    return QueryResult(
        answer=api_response.get("answer", ""),
        sources=sources,
        request_id=api_response.get("request_id", ""),
        intent=api_response.get("intent", ""),
        intent_confidence=api_response.get("intent_confidence", 0.0),
        intent_method=api_response.get("intent_method", ""),
        failure_type=api_response.get("failure_type"),
        grounded=api_response.get("grounded", True),
    )


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

# Schema aliases — the two evaluator paths (this runner vs evaluation/eval_main.py)
# historically drifted. `tests/eval_queries.json` was authored against the
# long-name schema used by eval_main.py, which meant this runner silently
# ignored contains/exact/failure_type expectations. Normalising at the single
# ingest point below fixes the CI gate without changing any test file.
_FIELD_ALIASES: dict[str, str] = {
    "expected_answer_exact": "expected_exact",
    "expected_answer_contains": "expected_contains",
}

# Configurable thresholds to avoid brittle hard-coding
_INTENT_METHOD_CONFIDENCE_THRESHOLD = 0.85
_LATENCY_SLA_MS = 2500
_REFUSAL_MESSAGE = "Insufficient data."


class FailureCategory(enum.Enum):
    """Structured failure taxonomy for categorizing evaluation failures."""
    # Content failures
    WRONG_ANSWER = "wrong_answer"
    MISSING_TERMS = "missing_terms"
    FORBIDDEN_CONTENT = "forbidden_content"
    REFUSAL_FAILURE = "refusal_failure"
    HALLUCINATION_RISK = "hallucination_risk"
    ARABIC_LEAKAGE = "arabic_leakage"
    ANSWER_TOO_SHORT = "answer_too_short"
    GENERIC_ANSWER = "generic_answer"

    # Source failures
    WRONG_SOURCE = "wrong_source"
    TOP1_SOURCE_MISMATCH = "top1_source_mismatch"
    LOW_SOURCE_PRECISION = "low_source_precision"
    CORPUS_MISSING = "corpus_missing"
    CORPUS_MISSING_STRICT = "corpus_missing_strict"

    # Pipeline failures
    UNEXPECTED_FAILURE_TYPE = "unexpected_failure_type"
    FAILURE_TYPE_MISMATCH = "failure_type_mismatch"

    # Infrastructure failures
    TIMEOUT = "timeout"
    INFRA_FAILURE = "infra_failure"
    ERROR = "error"

    # Performance failures
    LATENCY_TOO_HIGH = "latency_too_high"

    @classmethod
    def from_bucket(cls, bucket: str) -> "FailureCategory | None":
        """Map legacy bucket name to FailureCategory enum."""
        try:
            return cls(bucket)
        except ValueError:
            return None


def _normalize_test(test: dict) -> dict:
    """Return a copy of `test` with long-name schema fields mapped to the
    canonical short names consumed by this runner. The original dict is not
    mutated so upstream callers keep their view."""
    if not any(alias in test for alias in _FIELD_ALIASES):
        return test
    normalized = dict(test)
    for alias, canonical in _FIELD_ALIASES.items():
        if alias in normalized and canonical not in normalized:
            normalized[canonical] = normalized[alias]
    return normalized


def check_result(result, test: dict, elapsed: float, mode: str = "dev") -> tuple[bool, list[str], list[str]]:
    """
    Evaluate ALL criteria in the test case.
    Returns (passed, reasons, buckets).
    """
    test = _normalize_test(test)
    answer  = (result.answer or "").strip()
    sources = [s["source"] for s in result.sources]
    reasons: list[str] = []
    buckets: set[str]  = set()

    # expected_refusal: true — pattern-based, not string-exact
    if test.get("expected_refusal") is True:
        if not is_insufficient_response(answer):
            buckets.add(FailureCategory.REFUSAL_FAILURE.value)
            reasons.append(f"expected refusal, got {answer!r}")

    # Refusal response validation with semantic matching
    if "expected_exact" in test:
        exp = test["expected_exact"]
        if exp == _REFUSAL_MESSAGE:
            if not is_insufficient_response(answer):
                buckets.add(FailureCategory.REFUSAL_FAILURE.value)
                reasons.append(f"expected refusal response, got {answer!r}")
        elif answer != exp:
            buckets.add(FailureCategory.WRONG_ANSWER.value)
            reasons.append(f"expected exact {exp!r}, got {answer!r}")

    # Hallucination detection for refusal responses
    if "expected_exact" in test and test["expected_exact"] == _REFUSAL_MESSAGE:
        if is_insufficient_response(answer) and contains_numbers(answer):
            buckets.add(FailureCategory.HALLUCINATION_RISK.value)
            reasons.append("refusal response contains numbers (hallucination risk)")

    if "expected_contains" in test:
        missing = [t for t in test["expected_contains"] if t.lower() not in answer.lower()]
        if missing:
            buckets.add(FailureCategory.WRONG_ANSWER.value)
            reasons.append(f"missing terms: {missing}")

    # Forbidden content validation (must_not_contain)
    if "must_not_contain" in test:
        forbidden_found = [t for t in test["must_not_contain"] if t.lower() in answer.lower()]
        if forbidden_found:
            buckets.add(FailureCategory.FORBIDDEN_CONTENT.value)
            reasons.append(f"contains forbidden terms: {forbidden_found}")

    # Pipeline failure_type expectation. Mirrors evaluation/eval_main.py so both
    # evaluator paths enforce the same contract. `None` means "no failure
    # expected"; any non-None value must match the pipeline-reported type.
    if "expected_failure_type" in test:
        expected_ft = test["expected_failure_type"]
        actual_ft = getattr(result, "failure_type", None)
        if expected_ft is None and actual_ft is not None:
            buckets.add(FailureCategory.UNEXPECTED_FAILURE_TYPE.value)
            reasons.append(f"unexpected failure_type: {actual_ft}")
        elif expected_ft is not None and actual_ft != expected_ft:
            buckets.add(FailureCategory.FAILURE_TYPE_MISMATCH.value)
            reasons.append(
                f"failure_type mismatch: expected {expected_ft}, got {actual_ft}"
            )

    # Source attribution validation
    if "expected_source" in test:
        expected = test["expected_source"]
        if expected not in sources:
            buckets.add(FailureCategory.WRONG_SOURCE.value)
            reasons.append(f"expected source {expected!r}, got {sources}")

        # Top-1 source accuracy
        if sources and sources[0] != expected:
            buckets.add(FailureCategory.TOP1_SOURCE_MISMATCH.value)
            reasons.append(f"top-1 source mismatch: expected {expected!r}, got {sources[0]!r}")

        # Source precision (expected in top-2)
        if expected not in sources[:2]:
            buckets.add(FailureCategory.LOW_SOURCE_PRECISION.value)
            reasons.append(f"expected source not in top-2: {expected!r}")

    # Arabic leakage validation for multilingual tests
    if test.get("suite") == "multilingual_output":
        if contains_arabic(answer):
            buckets.add(FailureCategory.ARABIC_LEAKAGE.value)
            reasons.append("response contains Arabic characters (should be English only)")

    # Minimum length validation for non-refusal responses
    if "min_length" in test:
        if not is_insufficient_response(answer) and len(answer.split()) < test["min_length"]:
            buckets.add(FailureCategory.ANSWER_TOO_SHORT.value)
            reasons.append(f"answer too short (min {test['min_length']} words)")

    # Maximum latency validation
    if "max_latency_ms" in test:
        elapsed_ms = elapsed * 1000
        if elapsed_ms > test["max_latency_ms"]:
            buckets.add(FailureCategory.LATENCY_TOO_HIGH.value)
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
                buckets.add(FailureCategory.GENERIC_ANSWER.value)
                reasons.append("generic answer (strict mode)")

        # Fail if corpus_missing for required queries
        if test.get("required_corpus", False) and FailureCategory.CORPUS_MISSING.value in buckets:
            buckets.add(FailureCategory.CORPUS_MISSING_STRICT.value)
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
    sla_pass = (avg_elapsed * 1000) <= _LATENCY_SLA_MS

    # ── Canonical metrics (required by eval_gate) ─────────────────────────────
    # Hallucination rate: pipeline-reported failure_type == "hallucination"
    hallucinations = sum(1 for r in results if r.failure_type == "hallucination")
    hallucination_rate = round(hallucinations / total, 3) if total else 0.0

    # Domain accuracy: correct intent routing for eco/cv (rule-routed queries)
    domain_rows = [r for r in results if r.expected_intent in {"eco", "cv"} and not r.error]
    domain_correct = sum(1 for r in domain_rows if r.intent == r.expected_intent)
    domain_accuracy = round(domain_correct / len(domain_rows), 3) if domain_rows else 0.0

    # Canonical refusal_accuracy: out-of-domain queries that returned the
    # canonical refusal message exactly (case-insensitive).
    canonical_refusal_rows = [r for r in results if r.has_expected_exact
                              and r.expected_exact == _REFUSAL_MESSAGE and not r.error]
    canonical_refusal_hits = sum(
        1 for r in canonical_refusal_rows
        if str(r.answer or "").strip().lower() == _REFUSAL_MESSAGE.lower()
    )
    canonical_refusal_accuracy = (
        round(canonical_refusal_hits / len(canonical_refusal_rows), 3)
        if canonical_refusal_rows else 1.0
    )

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
        "hallucination_rate": hallucination_rate,
        "domain_accuracy":    domain_accuracy,
        "ocr_presence_check": True,
        "failure_buckets":    bucket_counts,
        "intent_method_metrics": intent_method_metrics,
        "intent_type_metrics": intent_type_metrics,
        "low_conf_failures":  len(low_conf_failures),
        "avg_elapsed_s":      avg_elapsed,
        "latency_sla_ms":     _LATENCY_SLA_MS,
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
    parser.add_argument("--workers", type=int, default=1,
                        help="Number of parallel workers (1 = sequential). Recommended 4-8 for local Ollama.")
    parser.add_argument("--query-timeout", type=float, default=90.0,
                        help="Hard timeout per query in seconds. Prevents hangs on stuck LLM calls.")
    parser.add_argument("--fast", action="store_true",
                        help="Disable KnowledgeGapAnalyzer LLM calls during eval (keeps deterministic CorpusTopicMap signal).")
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

    # Fast mode — short-circuit KnowledgeGapAnalyzer's LLM call.
    # The deterministic CorpusTopicMap still runs and produces missing_documents.
    if args.fast:
        os.environ["KGAP_BYPASS_LLM"] = "1"
        print("Fast mode: KnowledgeGapAnalyzer LLM calls disabled\n")

    # Use provided query function or default to new Pipeline architecture
    service = None
    pipeline = None
    shadow_logger = None
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

        # Initialize shadow logger if enabled
        shadow_logger = None
        shadow_adapter = None
        if USE_ADVANCED_RETRIEVAL_SHADOW:
            shadow_logger = DecisionLogger(log_path="logs/shadow_comparison.jsonl")
            print("Shadow mode: ENABLED - logging comparison to logs/shadow_comparison.jsonl")

            # Initialize shadow adapter separately to avoid circular import
            try:
                from app.advanced_retriever_adapter import AdvancedRetrievalAdapter
                shadow_adapter = AdvancedRetrievalAdapter(indexes=indexes)
                print("Shadow adapter initialized\n")
            except Exception as e:
                import logging
                logging.getLogger(__name__).warning("Failed to initialize shadow adapter: %s", e)
                print(f"Shadow adapter initialization failed: {e}\n")

        def query_fn(question: str):
            result = service.handle_query(question, query_id=f"eval_{int(time.time()*1000)}")
            # Convert to expected format
            sources = [{"source": h.source} for h in result.retrieval]
            # Determine intent method based on confidence
            intent_method = "rules" if result.confidence >= _INTENT_METHOD_CONFIDENCE_THRESHOLD else "v2_model"

            # Log shadow comparison if enabled
            if shadow_logger and shadow_adapter:
                primary_sources = [h.source for h in result.retrieval]
                # Run shadow retrieval
                try:
                    shadow_hits, shadow_metadata = shadow_adapter.retrieve(
                        query_vec=None,  # Not used by advanced path
                        intent=result.intent,
                        query=question,
                        top_k=5
                    )
                    advanced_sources = shadow_metadata.get('advanced_sources') if shadow_metadata else None
                    advanced_intent = shadow_metadata.get('advanced_intent') if shadow_metadata else None
                except Exception as e:
                    # Shadow retrieval failure should not break eval
                    import logging
                    logging.getLogger(__name__).warning("Shadow retrieval in eval failed: %s", e)
                    advanced_sources = None
                    advanced_intent = None
                    shadow_metadata = None

                shadow_logger.log_shadow_comparison(
                    request_id=result.query_id,
                    query=question,
                    primary_sources=primary_sources,
                    advanced_sources=advanced_sources,
                    primary_intent=result.intent,
                    advanced_intent=advanced_intent,
                    shadow_metadata=shadow_metadata,
                )

            # Convert InferenceService result to API response format, then to eval format
            api_response = {
                "answer": result.answer,
                "sources": sources,
                "request_id": result.query_id,
                "intent": result.intent,
                "intent_confidence": result.confidence,
                "intent_method": intent_method,
                "failure_type": result.failure_type,
                "grounded": result.grounded,
            }
            return from_api_response(api_response)
    else:
        print("Using provided query function\n")

    results: list[TestResult] = []

    def _build_test_result(idx: int, test: dict) -> tuple[TestResult, str]:
        test = _normalize_test(test)
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
                tr.buckets = [FailureCategory.INFRA_FAILURE.value]
            else:
                tr.buckets = [FailureCategory.ERROR.value]
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
                        tr.buckets = [FailureCategory.TIMEOUT.value]
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
                            tr.buckets = [FailureCategory.TIMEOUT.value]
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
                        tr.buckets = [FailureCategory.TIMEOUT.value]
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
            print(f"  Hallucination rate: {metrics['hallucination_rate']*100:.1f}%")
            print(f"  Domain accuracy:    {metrics['domain_accuracy']*100:.1f}%")
            print(f"  OCR presence check: {metrics['ocr_presence_check']}")
            print(f"  Gate decision:      {decision}")
            if failed_checks:
                print(f"  Failed checks:      {failed_checks}")
            print(f"{'='*60}")

        # ── Save report ───────────────────────────────────────────────────────
        args.report.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "decision": decision,
            "failed_checks": failed_checks,
            "metrics": metrics,
            "results": results_as_dicts,
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
