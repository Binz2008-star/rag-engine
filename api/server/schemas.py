"""Pydantic request/response schemas for the public API.

Shape is a 1:1 projection of `app.models.PipelineResult` — no field is added
that the canonical pipeline does not actually measure. `latency_ms` is a
single number because that is all the pipeline records; adding split
retrieval/generation timings would require instrumenting evaluated code and
re-running the strict gate.
"""

from __future__ import annotations

from typing import List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class QueryRequest(BaseModel):
    """Body for POST /api/query."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(..., min_length=1, max_length=4000)


class Source(BaseModel):
    """Single retrieved chunk surfaced to the UI."""

    model_config = ConfigDict(extra="ignore")

    source: str
    chunk_id: str = ""
    doc_type: str = ""
    score: float = 0.0


class QueryResponse(BaseModel):
    """Response for POST /api/query.

    Field parity with `PipelineResult`:

    * ``latency_ms``  — pipeline-measured end-to-end time
    * ``wall_ms``     — API wall-clock (includes thread hop + serialisation)
    * ``grounded`` / ``failure_type`` — same contract the eval gate enforces
    * ``intent_method`` — coarse class (``rules`` / ``v2_model``) matching
      the eval runner; the raw router label is kept under
      ``intent_method_raw`` for observability.
    """

    answer: str
    sources: List[Source] = Field(default_factory=list)
    latency_ms: int = 0
    wall_ms: int = 0
    request_id: str = ""
    intent: str = ""
    intent_confidence: float = 0.0
    intent_method: str = ""
    intent_method_raw: str = ""
    grounded: bool = True
    failure_type: Optional[str] = None
    model_version: str = ""
    retriever_version: str = ""


class HealthResponse(BaseModel):
    status: Literal["ok", "starting", "degraded", "error"]
    pipeline_ready: bool
    version: str
    chat_model: str
    index_count: int = 0
    detail: Optional[str] = None


class ErrorResponse(BaseModel):
    error: str
    detail: Optional[str] = None
