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


class DispatchRequest(BaseModel):
    question: str = Field(..., min_length=1)
    session_id: str | None = None
    user_id: str | None = None


class DispatchResponse(BaseModel):
    capability: str
    kind: str
    status: str
    request_id: str
    payload: dict[str, Any]


class CreateTaskRequest(BaseModel):
    title: str = Field(..., min_length=1)
    prompt: str = Field(..., min_length=1)
    intent: str = Field(..., min_length=1)
    session_id: str | None = None
    user_id: str | None = None


class TaskResponse(BaseModel):
    task_id: str
    title: str
    prompt: str
    intent: str
    status: str
    session_id: str | None = None
    user_id: str | None = None
    created_at: float
    updated_at: float


class ScheduleTaskRequest(BaseModel):
    task_id: str = Field(..., min_length=1)
    run_at: float


class ScheduleTaskResponse(BaseModel):
    task_id: str
    run_at: float
    status: str
    created_at: float


class ExecuteTaskRequest(BaseModel):
    task_id: str = Field(..., min_length=1)


class ExecuteTaskResponse(BaseModel):
    task_id: str
    status: str
    output: str
    started_at: float
    finished_at: float
