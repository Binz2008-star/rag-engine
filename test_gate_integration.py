"""
Integration tests for the canonical promotion gate.

Contract under test:
    pipeline → eval_main.run_eval → gate → decision
    eval_runner → report (JSON) → check_strict_pass.py → exit code

These tests do NOT hit Ollama or the real FAISS indexes. They use a fake
pipeline that yields deterministic `PipelineResult` objects so we can drive
the gate end-to-end without external services.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path

import pytest

from app.models import PipelineResult, RetrievalHit
from evaluation.eval_main import run_eval

REPO_ROOT = Path(__file__).parent


# ── Fake pipeline ─────────────────────────────────────────────────────────

@dataclass
class _FakePipeline:
    """Returns a scripted PipelineResult per query (by normalized query)."""
    scripted: dict[str, PipelineResult] = field(default_factory=dict)

    def run(self, query: str, query_id: str) -> PipelineResult:
        if query not in self.scripted:
            raise AssertionError(f"unexpected query in fake pipeline: {query!r}")
        result = self.scripted[query]
        result.query_id = query_id
        return result


def _ok_result(query: str, intent: str) -> PipelineResult:
    """A grounded, on-intent answer."""
    return PipelineResult(
        query_id="",
        query=query,
        normalized_query=query,
        intent=intent,
        confidence=1.0,
        intent_method="rule",
        retrieval=[
            RetrievalHit(
                chunk_id="c1",
                source="doc.txt",
                text="evidence",
                score=0.9,
                path="doc.txt",
                doc_type="text",
            )
        ],
        answer="Grounded answer.",
        grounded=True,
        failure_type=None,
    )


def _refusal_result(query: str, intent: str) -> PipelineResult:
    return PipelineResult(
        query_id="",
        query=query,
        normalized_query=query,
        intent=intent,
        confidence=1.0,
        intent_method="rule",
        retrieval=[],
        answer="Insufficient data.",
        grounded=True,
        failure_type="retrieval_miss",
    )


def _hallucinated_result(query: str, intent: str) -> PipelineResult:
    return PipelineResult(
        query_id="",
        query=query,
        normalized_query=query,
        intent=intent,
        confidence=1.0,
        intent_method="rule",
        retrieval=[
            RetrievalHit(
                chunk_id="c1",
                source="doc.txt",
                text="evidence",
                score=0.9,
                path="doc.txt",
                doc_type="text",
            )
        ],
        answer="A confidently wrong answer.",
        grounded=False,
        failure_type="hallucination",
    )


def _write_queries(tmp_path: Path, items: list[dict]) -> Path:
    path = tmp_path / "eval.json"
    path.write_text(json.dumps({"queries": items}), encoding="utf-8")
    return path


# ── eval_main → gate ──────────────────────────────────────────────────────

def test_run_eval_promotes_clean_run(tmp_path):
    queries = [
        {"query": "eco q", "expected_intent": "eco",
         "expected_answer_contains": ["answer"]},
        {"query": "cv q", "expected_intent": "cv",
         "expected_answer_contains": ["answer"]},
        {"query": "general q", "expected_intent": "general",
         "expected_refusal": True, "expected_answer_exact": "Insufficient data.",
         "expected_failure_type": "retrieval_miss"},
    ]
    pipeline = _FakePipeline(scripted={
        "eco q":     _ok_result("eco q", "eco"),
        "cv q":      _ok_result("cv q", "cv"),
        "general q": _refusal_result("general q", "general"),
    })

    report = run_eval(pipeline, _write_queries(tmp_path, queries), data_dir=None, strict=False)

    assert report["decision"] == "PROMOTE"
    assert report["failed_checks"] == []
    assert report["metrics"]["hallucination_rate"] == 0.0
    assert report["metrics"]["refusal_accuracy"] == 1.0
    assert report["metrics"]["domain_accuracy"] == 1.0


def test_run_eval_rejects_on_hallucination(tmp_path):
    queries = [
        {"query": "eco q", "expected_intent": "eco",
         "expected_answer_contains": ["answer"]},
    ]
    pipeline = _FakePipeline(scripted={
        "eco q": _hallucinated_result("eco q", "eco"),
    })

    report = run_eval(pipeline, _write_queries(tmp_path, queries), data_dir=None, strict=False)

    assert report["decision"] == "REJECT"
    assert "hallucination_rate" in report["failed_checks"]


def test_run_eval_rejects_on_refusal_failure(tmp_path):
    """Out-of-domain query that produces a grounded answer instead of refusal."""
    queries = [
        {"query": "general q", "expected_intent": "general",
         "expected_refusal": True, "expected_answer_exact": "Insufficient data.",
         "expected_failure_type": "retrieval_miss"},
    ]
    pipeline = _FakePipeline(scripted={
        "general q": _ok_result("general q", "general"),  # wrong: answers instead of refusing
    })

    report = run_eval(pipeline, _write_queries(tmp_path, queries), data_dir=None, strict=False)

    assert report["decision"] == "REJECT"
    assert "refusal_accuracy" in report["failed_checks"]


def test_run_eval_rejects_on_domain_miss(tmp_path):
    """eco query routed to general fails domain_accuracy."""
    queries = [
        {"query": "eco q", "expected_intent": "eco",
         "expected_answer_contains": ["answer"]},
    ]
    pipeline = _FakePipeline(scripted={
        "eco q": _ok_result("eco q", "general"),  # wrong intent
    })

    report = run_eval(pipeline, _write_queries(tmp_path, queries), data_dir=None, strict=False)

    assert report["decision"] == "REJECT"
    assert "domain_accuracy" in report["failed_checks"]


def test_run_eval_rejects_when_killer_query_fails(tmp_path):
    """A failing killer query must short-circuit the gate even if rate metrics pass."""
    queries = [
        {"query": "eco q", "expected_intent": "eco",
         "expected_answer_contains": ["answer"]},
        {"query": "killer q", "expected_intent": "general",
         "expected_refusal": True,
         "expected_answer_exact": "Insufficient data.",
         "expected_failure_type": "retrieval_miss",
         "killer": True},
    ]
    pipeline = _FakePipeline(scripted={
        "eco q":     _ok_result("eco q", "eco"),
        # Killer query answered instead of refusing — should be flagged.
        "killer q":  _ok_result("killer q", "general"),
    })

    report = run_eval(pipeline, _write_queries(tmp_path, queries), data_dir=None, strict=False)

    assert report["decision"] == "REJECT"
    assert "killer_failure" in report["failed_checks"]


def test_run_eval_promotes_when_killer_query_refuses_correctly(tmp_path):
    """A passing killer query must not cause REJECT on its own."""
    queries = [
        {"query": "eco q", "expected_intent": "eco",
         "expected_answer_contains": ["answer"]},
        {"query": "killer q", "expected_intent": "general",
         "expected_refusal": True,
         "expected_answer_exact": "Insufficient data.",
         "expected_failure_type": "retrieval_miss",
         "killer": True},
    ]
    pipeline = _FakePipeline(scripted={
        "eco q":     _ok_result("eco q", "eco"),
        "killer q":  _refusal_result("killer q", "general"),
    })

    report = run_eval(pipeline, _write_queries(tmp_path, queries), data_dir=None, strict=False)

    assert report["decision"] == "PROMOTE"
    assert "killer_failure" not in report["failed_checks"]


# ── check_strict_pass.py ──────────────────────────────────────────────────

CHECK_SCRIPT = REPO_ROOT / "scripts" / "check_strict_pass.py"
REPORT_PATH = REPO_ROOT / "reports" / "ci_eval_strict.json"


def _run_check_script() -> subprocess.CompletedProcess:
    return subprocess.run(
        [sys.executable, str(CHECK_SCRIPT)],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )


@pytest.fixture
def _isolated_report(tmp_path, monkeypatch):
    """Use isolated temp path for report to avoid race conditions."""
    report = tmp_path / "ci_eval_strict.json"
    monkeypatch.setenv("REPORT_PATH", str(report))
    return report


def test_check_strict_pass_exits_zero_on_promote(_isolated_report):
    _isolated_report.write_text(json.dumps({
        "decision": "PROMOTE",
        "failed_checks": [],
        "metrics": {
            "pass_rate": 1.0,
            "hallucination_rate": 0.0,
            "refusal_accuracy": 1.0,
            "domain_accuracy": 1.0,
            "ocr_presence_check": True,
        },
    }), encoding="utf-8")

    result = _run_check_script()

    assert result.returncode == 0
    assert "PASS" in result.stdout


def test_check_strict_pass_exits_nonzero_on_reject(_isolated_report):
    _isolated_report.write_text(json.dumps({
        "decision": "REJECT",
        "failed_checks": ["hallucination_rate"],
        "metrics": {
            "pass_rate": 0.9,
            "hallucination_rate": 0.1,
            "refusal_accuracy": 1.0,
            "domain_accuracy": 1.0,
            "ocr_presence_check": True,
        },
    }), encoding="utf-8")

    result = _run_check_script()

    assert result.returncode == 1
    assert "FAIL" in result.stdout
    assert "hallucination_rate" in result.stdout


def test_check_strict_pass_fails_if_decision_missing(_isolated_report):
    """Report without 'decision' must fail with exit 2 (not silently pass)."""
    _isolated_report.write_text(json.dumps({
        "metrics": {"pass_rate": 1.0},
    }), encoding="utf-8")

    result = _run_check_script()

    assert result.returncode == 2
