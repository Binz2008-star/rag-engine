"""Test reasoning verifier integration with grounding and reranker."""

import pytest
from unittest.mock import Mock, MagicMock
from generation.reasoning import ReasoningVerifier, ReasoningBreakdown
from app.models import RetrievalHit, FailureType


def test_reasoning_verifier_initialization():
    """Test ReasoningVerifier can be initialized."""
    verifier = ReasoningVerifier()
    assert verifier.premise_threshold == 0.5
    assert verifier.enable_speculation_check is True


def test_reasoning_verifier_no_hits():
    """Test reasoning verifier accepts when no hits available."""
    verifier = ReasoningVerifier()
    answer = "ECO Technology is a company."
    hits = []

    is_valid, breakdown = verifier.verify(answer, hits, None)
    assert is_valid is True
    assert breakdown.final_score == 1.0


def test_reasoning_verifier_insufficient_data():
    """Test reasoning verifier accepts insufficient data responses."""
    verifier = ReasoningVerifier()
    answer = "Insufficient data."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="Some context",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    is_valid, breakdown = verifier.verify(answer, hits, None)
    assert is_valid is True
    assert breakdown.final_score == 1.0


def test_reasoning_verifier_premise_support():
    """Test premise support check with lexical overlap."""
    verifier = ReasoningVerifier()
    answer = "ECO Technology provides environmental services."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology provides environmental protection services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    is_valid, breakdown = verifier.verify(answer, hits, None)
    assert is_valid is True
    assert breakdown.has_premise_support is True


def test_reasoning_verifier_speculative_rejection():
    """Test that speculative language is detected."""
    verifier = ReasoningVerifier()
    answer = "It appears that ECO Technology likely provides services."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology provides services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    is_valid, breakdown = verifier.verify(answer, hits, None)
    # Should have lower score due to speculation
    assert breakdown.avoids_speculation is False
    assert breakdown.final_score < 1.0


def test_reasoning_verifier_logical_flow():
    """Test logical flow detection with connectors."""
    verifier = ReasoningVerifier()
    answer = "ECO Technology provides services because it specializes in environmental protection."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology specializes in environmental protection services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    is_valid, breakdown = verifier.verify(answer, hits, None)
    assert breakdown.has_logical_flow is True


def test_reasoning_verifier_conclusion_link():
    """Test conclusion link via entity overlap."""
    verifier = ReasoningVerifier()
    answer = "ECO Technology was established in 2016."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology Environmental Protection Services was established in 2016.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    is_valid, breakdown = verifier.verify(answer, hits, None)
    assert breakdown.has_conclusion_link is True


def test_reasoning_verifier_semantic_premise_support():
    """Test semantic premise support with embedding function."""
    verifier = ReasoningVerifier()
    answer = "ECO Technology provides environmental services."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology offers environmental protection services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    # Mock embedding function
    mock_embed = Mock(return_value=[
        [0.1, 0.2, 0.3],  # answer sentence
        [0.1, 0.2, 0.3],  # context sentence (similar)
    ])

    is_valid, breakdown = verifier.verify(answer, hits, mock_embed)
    assert is_valid is True
    assert breakdown.has_premise_support is True


def test_reasoning_verifier_failure_type_exists():
    """Test that REASONING_REJECT failure type exists."""
    assert FailureType.REASONING_REJECT == "reasoning_reject"


def test_reasoning_verifier_configurable_threshold():
    """Test configurable premise threshold."""
    verifier = ReasoningVerifier(premise_threshold=0.8)
    assert verifier.premise_threshold == 0.8


def test_reasoning_verifier_disable_speculation_check():
    """Test disabling speculation check."""
    verifier = ReasoningVerifier(enable_speculation_check=False)
    assert verifier.enable_speculation_check is False

    answer = "It appears that ECO Technology likely provides services."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology provides services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    is_valid, breakdown = verifier.verify(answer, hits, None)
    # Should not penalize speculation when disabled
    assert breakdown.avoids_speculation is True


def test_reasoning_breakdown_dataclass():
    """Test ReasoningBreakdown dataclass structure."""
    breakdown = ReasoningBreakdown(
        has_premise_support=True,
        has_logical_flow=True,
        avoids_speculation=False,
        has_conclusion_link=True,
        final_score=0.75
    )
    assert breakdown.has_premise_support is True
    assert breakdown.has_logical_flow is True
    assert breakdown.avoids_speculation is False
    assert breakdown.has_conclusion_link is True
    assert breakdown.final_score == 0.75


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
