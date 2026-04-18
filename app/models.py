from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Optional


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
    failure_type: str | None = None
    latency_ms: int = 0
    model_version: str = ""
    retriever_version: str = ""
