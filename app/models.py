from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Optional


class FailureType(str, Enum):
    """Explicit failure type taxonomy for better debugging and monitoring.

    NOTE: INJECTION_REJECT is reserved for future use. There is currently
    no active injection detection gate in the pipeline. Prompt injection
    is handled via system prompt isolation, not a separate failure type.
    """
    ROUTING_MISS = "routing_miss"
    RETRIEVAL_EMPTY = "retrieval_empty"
    RETRIEVAL_LOW_SCORE = "retrieval_low_score"
    TERM_OVERLAP_MISS = "term_overlap_miss"
    GROUNDING_REJECT = "grounding_reject"
    SPECULATIVE_REJECT = "speculative_reject"
    REASONING_REJECT = "reasoning_reject"
    INJECTION_REJECT = "injection_reject"  # RESERVED: No active gate, future use only
    SENSITIVE_REJECT = "sensitive_reject"
    TRANSLATION_FAILURE = "translation_failure"


def normalize_legacy_failure_type(failure_type: str | None) -> str | None:
    """Normalize legacy failure_type labels to current taxonomy.

    Maps retired labels to their modern equivalents for backward compatibility
    with historical event data.

    Args:
        failure_type: Legacy failure_type string from historical events.

    Returns:
        Normalized failure_type string matching current FailureType enum,
        or None if input is None.
    """
    if failure_type is None:
        return None

    # Legacy label mappings
    legacy_map = {
        "retrieval_miss": "retrieval_empty",  # Most common legacy case
        "hallucination": "grounding_reject",    # Ungrounded answers
    }

    return legacy_map.get(failure_type, failure_type)


@dataclass
class Document:
    source: str
    path: str
    text: str
    doc_type: str
    modified_time: Optional[datetime] = None


@dataclass
class Chunk:
    chunk_id: str
    source: str
    text: str
    path: str
    doc_type: str
    offset: int = 0
    embedding: Any | None = None


@dataclass
class Route:
    intent: str
    confidence: float
    intent_method: str


@dataclass
class RetrievalHit:
    chunk_id: str
    source: str
    text: str
    score: float
    path: str
    doc_type: str
    page: int | None = None
    section: str | None = None


@dataclass
class RetrievedChunk:
    chunk: Chunk
    score: float


@dataclass
class RagResponse:
    answer: str
    sources: list[dict[str, str]]
    retrieval_time: float
    generation_time: float
    request_id: str = ""
    intent: str = ""
    intent_confidence: float = 0.0
    intent_method: str = ""


@dataclass
class KnowledgeGap:
    gap_type: str
    confidence_if_adversarial: float
    suggested_action: str
    missing_documents: list[str] = field(default_factory=list)
    missing_confidence: float = 0.0


@dataclass
class PipelineResult:
    query_id: str
    query: str
    normalized_query: str
    intent: str
    confidence: float
    intent_method: str
    retrieval: list[RetrievalHit] = field(default_factory=list)
    answer: str = ""
    grounded: bool = False
    failure_type: FailureType | None = None
    knowledge_gap: KnowledgeGap | None = None
    latency_ms: int = 0
    model_version: str = ""
    retriever_version: str = ""
    retry_attempts: int = 0
    corrected: bool = False
