"""Data models for RAG Assistant v1."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class Document:
    """Raw document loaded from file."""
    source: str
    path: str
    text: str
    doc_type: str
    modified_time: Optional[datetime] = None


@dataclass
class Chunk:
    """Text chunk with metadata."""
    chunk_id: str
    source: str
    text: str
    path: str
    doc_type: str
    offset: int = 0


@dataclass
class RetrievedChunk:
    """Chunk with retrieval score."""
    chunk: Chunk
    score: float


@dataclass
class RagResponse:
    """Complete RAG response with sources."""
    answer: str
    sources: list[dict[str, str]]
    retrieval_time: float
    generation_time: float
    request_id: str = ""
    intent_confidence: float = 0.0
    intent_method: str = ""
