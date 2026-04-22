from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class QueryRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None
    user_id: str | None = None


class TradingAnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None
    user_id: str | None = None


class AgentAnalyzeRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None
    user_id: str | None = None


class SourceItem(BaseModel):
    source: str
    chunk_id: str
    doc_type: str
    score: float


class QueryResponse(BaseModel):
    answer: str
    sources: list[SourceItem]
    latency_ms: int
    wall_ms: int
    request_id: str
    intent: str
    intent_confidence: float
    intent_method: str
    intent_method_raw: str
    grounded: bool
    failure_type: str | None
    model_version: str
    retriever_version: str


class TradingAnalyzeResponse(BaseModel):
    capability: str
    intent: str
    market: str | None
    asset: str | None
    timeframe: str | None
    prompt: str
    status: str


class AgentAnalyzeResponse(BaseModel):
    capability: str
    intent: str
    prompt: str
    summary: str
    suggested_tools: list[str]
    status: str


class HealthResponse(BaseModel):
    status: str
    pipeline_ready: bool
    version: str
    chat_model: str
    index_count: int | None = None
    detail: str | None = None


class ErrorResponse(BaseModel):
    error: str | None = None
    detail: str | list[dict[str, Any]]


class SystemHealthResponse(BaseModel):
    version: str
    pipeline_ready: bool
    index_count: int | None = None
    guardian: dict[str, object]
