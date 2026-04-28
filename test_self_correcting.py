"""Test self-correcting generation pipeline."""

import pytest
from unittest.mock import Mock, MagicMock
from generation.self_correcting import SelfCorrectingGenerator, RetryAttempt, CorrectionResult
from app.models import FailureType, RetrievalHit


def test_self_correcting_initialization():
    """Test SelfCorrectingGenerator can be initialized."""
    generator = SelfCorrectingGenerator()
    assert generator.max_retries == 2
    assert generator.enable_grounding_retry is True
    assert generator.enable_reasoning_retry is True


def test_self_correcting_custom_config():
    """Test SelfCorrectingGenerator with custom configuration."""
    generator = SelfCorrectingGenerator(max_retries=3, enable_grounding_retry=False)
    assert generator.max_retries == 3
    assert generator.enable_grounding_retry is False


def test_self_correcting_no_correction_needed():
    """Test that no correction occurs when initial attempt passes."""
    generator = SelfCorrectingGenerator(max_retries=2)
    answer = "ECO Technology provides environmental services."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology provides environmental protection services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    # Mock functions
    generate_fn = Mock(return_value=answer)
    check_grounding_fn = Mock(return_value=True)
    check_reasoning_fn = Mock(return_value=(True, None))

    result = generator.correct(
        query="What does ECO Technology do?",
        initial_answer=answer,
        hits=hits,
        initial_failure_type=None,
        initial_grounded=True,
        initial_reasoning_valid=True,
        generate_fn=generate_fn,
        check_grounding_fn=check_grounding_fn,
        check_reasoning_fn=check_reasoning_fn,
    )

    assert result.corrected is False
    assert result.total_attempts == 1
    assert result.final_answer == answer
    assert len(result.attempts) == 1
    assert result.attempts[0].strategy == "initial"


def test_self_correcting_grounding_failure():
    """Test self-correction for grounding failure."""
    generator = SelfCorrectingGenerator(max_retries=2)
    initial_answer = "ECO Technology provides services."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology provides environmental protection services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    # Mock functions - first fails grounding, second passes
    generate_fn = Mock(side_effect=["ECO Technology provides services.", "ECO Technology provides environmental protection services."])
    check_grounding_fn = Mock(side_effect=[False, True])
    check_reasoning_fn = Mock(return_value=(True, None))

    result = generator.correct(
        query="What does ECO Technology do?",
        initial_answer=initial_answer,
        hits=hits,
        initial_failure_type=FailureType.GROUNDING_REJECT,
        initial_grounded=False,
        initial_reasoning_valid=True,
        generate_fn=generate_fn,
        check_grounding_fn=check_grounding_fn,
        check_reasoning_fn=check_reasoning_fn,
    )

    assert result.corrected is True
    assert result.total_attempts == 3  # initial + 2 retries
    assert result.final_grounded is True
    assert len(result.attempts) == 3


def test_self_correcting_reasoning_failure():
    """Test self-correction for reasoning failure."""
    generator = SelfCorrectingGenerator(max_retries=2)
    initial_answer = "It appears ECO Technology likely provides services."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology provides environmental protection services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    # Mock functions - first fails reasoning, second passes
    generate_fn = Mock(side_effect=["It appears ECO Technology likely provides services.", "ECO Technology provides environmental protection services."])
    check_grounding_fn = Mock(return_value=True)
    check_reasoning_fn = Mock(side_effect=[(False, None), (True, None)])

    result = generator.correct(
        query="What does ECO Technology do?",
        initial_answer=initial_answer,
        hits=hits,
        initial_failure_type=FailureType.REASONING_REJECT,
        initial_grounded=True,
        initial_reasoning_valid=False,
        generate_fn=generate_fn,
        check_grounding_fn=check_grounding_fn,
        check_reasoning_fn=check_reasoning_fn,
    )

    assert result.corrected is True
    assert result.total_attempts == 3  # initial + 2 retries
    assert result.final_reasoning_valid is True
    assert len(result.attempts) == 3


def test_self_correcting_exhausted_retries():
    """Test behavior when all retries are exhausted."""
    generator = SelfCorrectingGenerator(max_retries=1)
    initial_answer = "ECO Technology provides services."
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology provides environmental protection services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    # Mock functions - all attempts fail grounding
    generate_fn = Mock(side_effect=["ECO Technology provides services.", "ECO Technology provides services."])
    check_grounding_fn = Mock(return_value=False)
    check_reasoning_fn = Mock(return_value=(True, None))

    result = generator.correct(
        query="What does ECO Technology do?",
        initial_answer=initial_answer,
        hits=hits,
        initial_failure_type=FailureType.GROUNDING_REJECT,
        initial_grounded=False,
        initial_reasoning_valid=True,
        generate_fn=generate_fn,
        check_grounding_fn=check_grounding_fn,
        check_reasoning_fn=check_reasoning_fn,
    )

    assert result.corrected is False
    assert result.total_attempts == 2  # initial + 1 retry
    assert result.final_grounded is False
    assert len(result.attempts) == 2


def test_self_correcting_strategy_selection():
    """Test that correct strategy is selected based on failure type."""
    generator = SelfCorrectingGenerator()

    # Grounding failure
    strategy = generator._select_strategy(FailureType.GROUNDING_REJECT, False, True)
    assert strategy == "grounding_strict"

    # Reasoning failure
    strategy = generator._select_strategy(FailureType.REASONING_REJECT, True, False)
    assert strategy == "reasoning_explicit"

    # Speculative failure
    strategy = generator._select_strategy(FailureType.SPECULATIVE_REJECT, True, True)
    assert strategy == "anti_speculation"

    # General failure
    strategy = generator._select_strategy(None, True, True)
    assert strategy == "general_rephrase"


def test_self_correcting_should_retry():
    """Test retry decision logic."""
    generator = SelfCorrectingGenerator(max_retries=2)

    # Should retry if grounded fails
    assert generator._should_retry(FailureType.GROUNDING_REJECT, False, True, 1) is True

    # Should retry if reasoning fails
    assert generator._should_retry(FailureType.REASONING_REJECT, True, False, 1) is True

    # Should not retry if both pass
    assert generator._should_retry(None, True, True, 1) is False

    # Should not retry if max retries exceeded
    assert generator._should_retry(FailureType.GROUNDING_REJECT, False, True, 3) is False

    # Should not retry if grounding retry disabled
    generator_no_grounding = SelfCorrectingGenerator(enable_grounding_retry=False)
    assert generator_no_grounding._should_retry(FailureType.GROUNDING_REJECT, False, True, 1) is False


def test_self_correcting_prompt_building():
    """Test that different strategies build different prompts."""
    generator = SelfCorrectingGenerator()
    query = "What does ECO Technology do?"
    hits = [RetrievalHit(
        chunk_id="1",
        source="test.pdf",
        text="ECO Technology provides environmental protection services.",
        score=0.8,
        path="/test.pdf",
        doc_type="pdf"
    )]

    # Grounding strict prompt
    prompt = generator._build_correction_prompt(query, hits, "grounding_strict", 1)
    assert "STRICT INSTRUCTIONS" in prompt
    assert "ONLY using information explicitly stated" in prompt

    # Reasoning explicit prompt
    prompt = generator._build_correction_prompt(query, hits, "reasoning_explicit", 1)
    assert "REASONING INSTRUCTIONS" in prompt
    assert "step by step" in prompt
    assert "logical connectors" in prompt

    # Anti-speculation prompt
    prompt = generator._build_correction_prompt(query, hits, "anti_speculation", 1)
    assert "ANTI-SPECULATION INSTRUCTIONS" in prompt
    assert "DO NOT use speculative language" in prompt


def test_retry_attempt_dataclass():
    """Test RetryAttempt dataclass structure."""
    attempt = RetryAttempt(
        attempt_number=1,
        strategy="grounding_strict",
        answer="ECO Technology provides environmental services.",
        grounded=True,
        reasoning_valid=True,
        failure_type=None,
    )
    assert attempt.attempt_number == 1
    assert attempt.strategy == "grounding_strict"
    assert attempt.grounded is True


def test_correction_result_dataclass():
    """Test CorrectionResult dataclass structure."""
    result = CorrectionResult(
        final_answer="ECO Technology provides environmental services.",
        final_grounded=True,
        final_reasoning_valid=True,
        final_failure_type=None,
        total_attempts=2,
        attempts=[],
        corrected=True,
    )
    assert result.corrected is True
    assert result.total_attempts == 2


def test_get_retry_metrics():
    """Test retry metrics extraction."""
    generator = SelfCorrectingGenerator()
    result = CorrectionResult(
        final_answer="ECO Technology provides environmental services.",
        final_grounded=True,
        final_reasoning_valid=True,
        final_failure_type=None,
        total_attempts=3,
        attempts=[
            RetryAttempt(0, "initial", "answer1", False, True, FailureType.GROUNDING_REJECT),
            RetryAttempt(1, "grounding_strict", "answer2", True, True, None),
        ],
        corrected=True,
    )

    metrics = generator.get_retry_metrics(result)
    assert metrics["total_attempts"] == 3
    assert metrics["corrected"] is True
    assert "grounding_strict" in metrics["strategies_used"]
    assert metrics["final_failure_type"] is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
