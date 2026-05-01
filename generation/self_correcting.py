"""Self-correcting generation pipeline with retry strategies."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Callable

from app.models import FailureType, RetrievalHit

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class RetryAttempt:
    """Details of a retry attempt."""
    attempt_number: int
    strategy: str
    answer: str
    grounded: bool
    reasoning_valid: bool
    failure_type: FailureType | None


@dataclass(frozen=True)
class CorrectionResult:
    """Result of self-correction process."""
    final_answer: str
    final_grounded: bool
    final_reasoning_valid: bool
    final_failure_type: FailureType | None
    total_attempts: int
    attempts: list[RetryAttempt]
    corrected: bool


class SelfCorrectingGenerator:
    """Self-correcting generation with retry strategies for different failure types."""

    def __init__(
        self,
        max_retries: int = 2,
        enable_grounding_retry: bool = True,
        enable_reasoning_retry: bool = True,
    ) -> None:
        self.max_retries = max_retries
        self.enable_grounding_retry = enable_grounding_retry
        self.enable_reasoning_retry = enable_reasoning_retry

    def correct(
        self,
        query: str,
        initial_answer: str,
        hits: list[RetrievalHit],
        initial_failure_type: FailureType | None,
        initial_grounded: bool,
        initial_reasoning_valid: bool,
        generate_fn: Callable[[str, str], str],
        check_grounding_fn: Callable[[str, list[RetrievalHit]], bool],
        check_reasoning_fn: Callable[[str, list[RetrievalHit]], tuple[bool, object]],
    ) -> CorrectionResult:
        """
        Attempt to correct a failed generation using retry strategies.

        Args:
            query: Original query
            initial_answer: Initial generated answer
            hits: Retrieved context chunks
            initial_failure_type: Failure type from initial attempt
            initial_grounded: Whether initial answer was grounded
            initial_reasoning_valid: Whether initial answer passed reasoning check
            generate_fn: Function to generate answer (query, prompt) -> answer
            check_grounding_fn: Function to check grounding (answer, hits) -> bool
            check_reasoning_fn: Function to check reasoning (answer, hits) -> (bool, breakdown)

        Returns:
            CorrectionResult with final answer and attempt details
        """
        attempts = []

        # Record initial attempt
        attempts.append(RetryAttempt(
            attempt_number=0,
            strategy="initial",
            answer=initial_answer,
            grounded=initial_grounded,
            reasoning_valid=initial_reasoning_valid,
            failure_type=initial_failure_type,
        ))

        # If initial attempt passed, return immediately
        if initial_grounded and initial_reasoning_valid:
            return CorrectionResult(
                final_answer=initial_answer,
                final_grounded=initial_grounded,
                final_reasoning_valid=initial_reasoning_valid,
                final_failure_type=initial_failure_type,
                total_attempts=1,
                attempts=attempts,
                corrected=False,
            )

        # Determine retry strategy based on failure type
        strategy = self._select_strategy(initial_failure_type, initial_grounded, initial_reasoning_valid)

        # Attempt retries
        for attempt_num in range(1, self.max_retries + 1):
            if not self._should_retry(initial_failure_type, initial_grounded, initial_reasoning_valid, attempt_num):
                break

            logger.info(f"Self-correction attempt {attempt_num}/{self.max_retries} using strategy: {strategy}")

            # Generate modified prompt based on strategy
            modified_prompt = self._build_correction_prompt(query, hits, strategy, attempt_num)

            # Generate new answer
            retry_answer = generate_fn(query, modified_prompt)

            # Check grounding
            retry_grounded = check_grounding_fn(retry_answer, hits)

            # Check reasoning
            retry_reasoning_valid, _ = check_reasoning_fn(retry_answer, hits)

            # Determine failure type
            retry_failure_type = None
            if not retry_grounded:
                retry_failure_type = FailureType.GROUNDING_REJECT
            elif not retry_reasoning_valid:
                retry_failure_type = FailureType.REASONING_REJECT

            # Record attempt
            attempts.append(RetryAttempt(
                attempt_number=attempt_num,
                strategy=strategy,
                answer=retry_answer,
                grounded=retry_grounded,
                reasoning_valid=retry_reasoning_valid,
                failure_type=retry_failure_type,
            ))

            # If retry succeeded, return
            if retry_grounded and retry_reasoning_valid:
                logger.info(f"Self-correction succeeded on attempt {attempt_num}")
                return CorrectionResult(
                    final_answer=retry_answer,
                    final_grounded=retry_grounded,
                    final_reasoning_valid=retry_reasoning_valid,
                    final_failure_type=retry_failure_type,
                    total_attempts=attempt_num + 1,
                    attempts=attempts,
                    corrected=True,
                )

            # Update strategy for next attempt if needed
            strategy = self._select_strategy(retry_failure_type, retry_grounded, retry_reasoning_valid)

        # All retries exhausted, return best attempt
        # Prefer the last attempt (most aggressive correction)
        best_attempt = attempts[-1]
        logger.warning(f"Self-correction exhausted after {len(attempts)} attempts")

        return CorrectionResult(
            final_answer=best_attempt.answer,
            final_grounded=best_attempt.grounded,
            final_reasoning_valid=best_attempt.reasoning_valid,
            final_failure_type=best_attempt.failure_type,
            total_attempts=len(attempts),
            attempts=attempts,
            corrected=False,
        )

    def _select_strategy(
        self,
        failure_type: FailureType | None,
        grounded: bool,
        reasoning_valid: bool,
    ) -> str:
        """Select retry strategy based on failure type."""
        if not grounded:
            return "grounding_strict"
        if not reasoning_valid:
            return "reasoning_explicit"
        if failure_type == FailureType.SPECULATIVE_REJECT:
            return "anti_speculation"
        return "general_rephrase"

    def _should_retry(
        self,
        failure_type: FailureType | None,
        grounded: bool,
        reasoning_valid: bool,
        attempt_num: int,
    ) -> bool:
        """Determine if retry should be attempted."""
        if attempt_num > self.max_retries:
            return False

        # Don't retry if already passed
        if grounded and reasoning_valid:
            return False

        # Check if retry is enabled for this failure type
        if not grounded and not self.enable_grounding_retry:
            return False
        if not reasoning_valid and not self.enable_reasoning_retry:
            return False

        return True

    def _build_correction_prompt(
        self,
        query: str,
        hits: list[RetrievalHit],
        strategy: str,
        attempt_num: int,
    ) -> str:
        """Build modified prompt for retry attempt."""
        context = "\n\n".join(f"[{i+1}] {hit.text}" for i, hit in enumerate(hits[:3]))

        base_prompt = f"""Answer the following question using ONLY the provided context.

Context:
{context}

Question: {query}

"""

        if strategy == "grounding_strict":
            return base_prompt + """
STRICT INSTRUCTIONS:
- Answer ONLY using information explicitly stated in the context
- Do NOT infer or add information not present in the context
- If the answer is not in the context, respond with "Insufficient data."
- Use direct quotes from the context when possible
"""

        elif strategy == "reasoning_explicit":
            return base_prompt + """
REASONING INSTRUCTIONS:
- Show your reasoning step by step
- Use logical connectors (because, therefore, thus, consequently)
- Connect each claim to evidence in the context
- Avoid speculative language (likely, probably, appears)
- Ensure your conclusion directly follows from the premises
"""

        elif strategy == "anti_speculation":
            return base_prompt + """
ANTI-SPECULATION INSTRUCTIONS:
- DO NOT use speculative language (likely, probably, appears, seems)
- State only what is explicitly supported by the context
- Avoid hedging or uncertainty
- If you cannot answer with certainty, respond with "Insufficient data."
"""

        elif strategy == "general_rephrase":
            return base_prompt + """
REPHRASE INSTRUCTIONS:
- Provide a clear, direct answer
- Focus on the most relevant information from context
- Keep the answer concise and factual
"""

        else:
            return base_prompt

    def get_retry_metrics(self, correction_result: CorrectionResult) -> dict:
        """Extract retry metrics from correction result."""
        return {
            "total_attempts": correction_result.total_attempts,
            "corrected": correction_result.corrected,
            "strategies_used": list(set(a.strategy for a in correction_result.attempts)),
            "final_failure_type": correction_result.final_failure_type.value if correction_result.final_failure_type else None,
        }
