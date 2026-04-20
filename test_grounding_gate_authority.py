"""
Regression guard: `check_grounding()` is the SOLE authoritative grounding gate.

Protects the v1.0 invariant (tag `v1.0-strict-promote`) established by PR #6:
the runtime pipeline and the evaluator must agree on what "grounded" means,
and the weaker token-overlap layer (`_is_grounded`) that caused the
split-brain defect must NOT be re-introduced.

Two layers of enforcement:
    1. Behavior tests  - run the pipeline with mocked `check_grounding` and
       assert the rejection path forces `Insufficient data.` +
       `retrieval_miss`.
    2. Static invariant - scan `app/pipeline.py` source and reject any
       re-introduction of a weaker grounding helper.

These tests MUST NOT require Ollama, FAISS indexes, or any external
service.  They run as part of the normal pytest suite so CI fails fast
on any drift from the v1.0 contract.
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np

from app.models import KnowledgeGap, RetrievalHit, Route


# --------------------------------------------------------------------------- #
# Minimal fakes to construct Pipeline without Ollama / FAISS / requests       #
# --------------------------------------------------------------------------- #


class _FakeRouter:
    def route(self, normalized_query: str) -> Route:
        return Route(intent="eco", confidence=1.0, intent_method="rule")


class _FakeKnowledgeGapAnalyzer:
    """
    Injected so the Pipeline never lazy-imports analysis.knowledge_gap
    (which pulls in the `requests` runtime dep absent from the
    lightweight CI lane).
    """

    def analyze(self, query: str, intent: str, normalized_query: str) -> KnowledgeGap:
        return KnowledgeGap(
            gap_type="missing_information",
            confidence_if_adversarial=0.0,
            suggested_action="add_relevant_documents",
        )


class _FakeEmbedder:
    """Deterministic unit-vector embeddings; never touches Ollama."""

    dim = 8

    def embed_batch(self, texts):
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for i, _ in enumerate(texts):
            out[i, i % self.dim] = 1.0
        return out


class _FakeRetriever:
    version = "fake_v1"

    def __init__(self, hits: list[RetrievalHit]):
        self._hits = hits
        self.indexes: dict = {}  # CorpusTopicMap iterates this; empty is fine.

    def retrieve(self, query_vec, intent: str, query: str) -> list[RetrievalHit]:
        return list(self._hits)


class _FakeLLM:
    def __init__(self, canned_answer: str):
        self._answer = canned_answer

    def generate(self, query: str, hits) -> str:
        return self._answer


def _hit(text: str, score: float = 0.9) -> RetrievalHit:
    return RetrievalHit(
        chunk_id=f"chunk-{score}",
        source="fake.pdf",
        text=text,
        score=score,
        path="/fake/fake.pdf",
        doc_type="eco",
    )


# --------------------------------------------------------------------------- #
# Pipeline construction                                                       #
# --------------------------------------------------------------------------- #


def _build_pipeline(llm_answer: str, context_text: str = "ECO provides wastewater services."):
    """Construct a real Pipeline with fake dependencies."""
    # Import inside the helper so monkeypatches on app.pipeline.check_grounding
    # (applied per-test) rebind before the Pipeline is used.
    from app.pipeline import Pipeline

    retriever = _FakeRetriever([_hit(context_text)])
    llm = _FakeLLM(llm_answer)
    return Pipeline(
        router=_FakeRouter(),
        embedder=_FakeEmbedder(),
        retriever=retriever,
        llm=llm,
        reranker=None,
        knowledge_gap_analyzer=_FakeKnowledgeGapAnalyzer(),
    )


# --------------------------------------------------------------------------- #
# Behavior tests                                                              #
# --------------------------------------------------------------------------- #


def test_ungrounded_answer_is_forced_to_refusal(monkeypatch):
    """
    When `check_grounding()` rejects the LLM output, the pipeline MUST
    replace it with the canonical refusal and classify as retrieval_miss.
    This is the v1.0 contract: the evaluator's verdict is binding at runtime.
    """
    import app.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "check_grounding", lambda *a, **kw: False)

    pipeline = _build_pipeline(
        llm_answer="ECO was founded in 1995 and operates in 12 countries.",
        context_text="ECO provides wastewater services.",
    )
    result = pipeline.run("What is ECO?", query_id="test-ungrounded")

    assert result.answer == "Insufficient data.", (
        "Ungrounded LLM output must be replaced with the canonical refusal. "
        "Pipeline shipped ungrounded content — v1.0 grounding contract violated."
    )
    assert result.failure_type == "retrieval_miss"
    assert result.grounded is True  # refusal is trivially grounded


def test_grounded_answer_is_preserved(monkeypatch):
    """
    When `check_grounding()` accepts the LLM output, the pipeline MUST
    pass it through unchanged. This confirms the gate is not over-rejecting.
    """
    import app.pipeline as pipeline_module

    monkeypatch.setattr(pipeline_module, "check_grounding", lambda *a, **kw: True)

    grounded_answer = "ECO provides wastewater services."
    pipeline = _build_pipeline(
        llm_answer=grounded_answer,
        context_text=grounded_answer,
    )
    result = pipeline.run("What does ECO do?", query_id="test-grounded")

    assert result.answer == grounded_answer
    assert result.failure_type is None
    assert result.grounded is True


def test_grounding_gate_is_called_on_real_answer(monkeypatch):
    """
    Hard proof that the runtime path actually invokes `check_grounding`.
    A future refactor that routes around the gate will fail this test
    even if the behavior tests above coincidentally still pass.
    """
    import app.pipeline as pipeline_module

    call_log: list[tuple] = []

    def _spy(answer, hits, embed_fn, threshold=0.60):
        call_log.append((answer, len(hits)))
        return True

    monkeypatch.setattr(pipeline_module, "check_grounding", _spy)

    pipeline = _build_pipeline(llm_answer="ECO provides wastewater services.")
    pipeline.run("What does ECO do?", query_id="test-gate-called")

    assert call_log, (
        "check_grounding() was never called on the runtime path. "
        "The authoritative grounding gate has been bypassed — "
        "v1.0 contract violated."
    )


# --------------------------------------------------------------------------- #
# Static invariants — source-level guard against re-introduction              #
# --------------------------------------------------------------------------- #


_PIPELINE_SOURCE = (
    Path(__file__).parent / "app" / "pipeline.py"
).read_text(encoding="utf-8")


def test_pipeline_imports_check_grounding():
    """Pipeline must import the canonical grounding function."""
    assert re.search(
        r"from\s+generation\.grounding\s+import\s+check_grounding",
        _PIPELINE_SOURCE,
    ), (
        "app/pipeline.py must import check_grounding from generation.grounding. "
        "Without this import the authoritative gate cannot run."
    )


def test_pipeline_calls_check_grounding():
    """Pipeline source must contain at least one call to `check_grounding(`."""
    assert "check_grounding(" in _PIPELINE_SOURCE, (
        "app/pipeline.py no longer calls check_grounding(). "
        "The authoritative grounding gate has been removed — "
        "v1.0 contract violated."
    )


def test_weaker_is_grounded_helper_is_not_reintroduced():
    """
    The original defect was a weaker `_is_grounded` token-overlap helper
    shadowing the evaluator's semantic check. That helper was removed in
    PR #6. Its re-introduction is forbidden.

    Note: `_has_sufficient_overlap` is a DIFFERENT function (retrieval
    recall gate, not grounding gate) and is allowed.
    """
    forbidden = re.search(r"def\s+_is_grounded\s*\(", _PIPELINE_SOURCE)
    assert not forbidden, (
        "A `_is_grounded` helper has been re-introduced in app/pipeline.py. "
        "This was the root cause of the pre-v1.0 split-brain defect "
        "(pipeline token-overlap 0.5 disagreeing with evaluator semantic 0.60). "
        "Grounding must be enforced ONLY via check_grounding()."
    )
