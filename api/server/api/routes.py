from __future__ import annotations

import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from ..core.config import get_settings
from ..schemas import (
    AgentAnalyzeRequest,
    AgentAnalyzeResponse,
    DispatchRequest,
    DispatchResponse,
    ErrorResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    SystemHealthResponse,
    TradingAnalyzeRequest,
    TradingAnalyzeResponse,
)
from ..services.agent_service import AgentService
from ..services.capability_router import Capability, CapabilityRouter
from ..services.context_service import ContextService, InteractionRecord
from ..services.health_guardian import HealthGuardian
from ..services.interaction_log_service import InteractionLogService, LoggedRequest
from ..services.rag_service import PipelineNotReadyError, RagService
from ..services.trading_service import TradingService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["rag"])


def _rag_service(request: Request) -> RagService:
    service: RagService | None = getattr(request.app.state, "rag_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="RAG service not initialised",
        )
    return service


def _trading_service(request: Request) -> TradingService:
    service: TradingService | None = getattr(request.app.state, "trading_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trading service not initialised",
        )
    return service


def _agent_service(request: Request) -> AgentService:
    service: AgentService | None = getattr(request.app.state, "agent_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent service not initialised",
        )
    return service


def _capability_router(request: Request) -> CapabilityRouter:
    router_service: CapabilityRouter | None = getattr(
        request.app.state, "capability_router", None
    )
    if router_service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Capability router not initialised",
        )
    return router_service


def _context_service(request: Request) -> ContextService | None:
    return getattr(request.app.state, "context_service", None)


def _interaction_log_service(request: Request) -> InteractionLogService | None:
    return getattr(request.app.state, "interaction_log_service", None)


def _health_guardian(request: Request) -> HealthGuardian:
    guardian: HealthGuardian | None = getattr(request.app.state, "health_guardian", None)
    if guardian is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Health guardian not initialised",
        )
    return guardian


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: {"model": ErrorResponse}},
)
async def health(request: Request) -> HealthResponse:
    settings = get_settings()
    service: RagService | None = getattr(request.app.state, "rag_service", None)

    if service is None:
        return HealthResponse(
            status="starting",
            pipeline_ready=False,
            version=settings.version,
            chat_model=settings.chat_model,
            detail="Service not mounted yet",
        )

    return HealthResponse(
        status="ok" if service.ready else "starting",
        pipeline_ready=service.ready,
        version=settings.version,
        chat_model=settings.chat_model,
        index_count=service.index_count,
    )


@router.get(
    "/system/health",
    response_model=SystemHealthResponse,
    responses={503: {"model": ErrorResponse}},
)
async def system_health(request: Request) -> SystemHealthResponse:
    settings = get_settings()
    guardian = _health_guardian(request)
    service: RagService | None = getattr(request.app.state, "rag_service", None)

    pipeline_ready = bool(service and service.ready)
    index_count = service.index_count if service is not None else None

    guardian_report = await guardian.full_report(
        ollama_base_url=settings.ollama_base_url,
        index_dir=str(settings.index_dir),
        rag_ready=pipeline_ready,
        index_count=index_count,
    )

    return SystemHealthResponse(
        version=settings.version,
        pipeline_ready=pipeline_ready,
        index_count=index_count,
        guardian=guardian_report,
    )


@router.post(
    "/trading/analyze",
    response_model=TradingAnalyzeResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def trading_analyze(
    payload: TradingAnalyzeRequest,
    request: Request,
) -> TradingAnalyzeResponse:
    settings = get_settings()
    trading_service = _trading_service(request)

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty")
    if len(question) > settings.max_question_length:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Question exceeds max length "
                f"({settings.max_question_length} chars)"
            ),
        )

    try:
        result = trading_service.analyze(question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Trading analyze failed")
        raise HTTPException(
            status_code=500, detail="Internal error while processing trading analysis"
        ) from exc

    return TradingAnalyzeResponse(
        capability=result.capability,
        intent=result.intent,
        market=result.market,
        asset=result.asset,
        timeframe=result.timeframe,
        prompt=result.prompt,
        status=result.status,
    )


@router.post(
    "/agent/analyze",
    response_model=AgentAnalyzeResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def agent_analyze(
    payload: AgentAnalyzeRequest,
    request: Request,
) -> AgentAnalyzeResponse:
    settings = get_settings()
    agent_service = _agent_service(request)

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty")
    if len(question) > settings.max_question_length:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Question exceeds max length "
                f"({settings.max_question_length} chars)"
            ),
        )

    try:
        result = agent_service.analyze(question)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Agent analyze failed")
        raise HTTPException(
            status_code=500, detail="Internal error while processing agent analysis"
        ) from exc

    return AgentAnalyzeResponse(
        capability=result.capability,
        intent=result.intent,
        prompt=result.prompt,
        summary=result.summary,
        suggested_tools=result.suggested_tools,
        status=result.status,
    )


@router.post(
    "/query",
    response_model=QueryResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def query(payload: QueryRequest, request: Request) -> QueryResponse:
    settings = get_settings()
    service = _rag_service(request)
    capability_router = _capability_router(request)
    context_service = _context_service(request)
    interaction_log_service = _interaction_log_service(request)

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty")
    if len(question) > settings.max_question_length:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Question exceeds max length "
                f"({settings.max_question_length} chars)"
            ),
        )

    route = capability_router.route(question)
    if route.capability == Capability.TRADING:
        raise HTTPException(
            status_code=400,
            detail="Trading capability is not enabled yet.",
        )
    if route.capability == Capability.ADMIN:
        raise HTTPException(
            status_code=400,
            detail="Admin capability is not exposed on this endpoint.",
        )

    request_started = time.time()
    request_id = str(uuid.uuid4())

    try:
        result = await service.query(question)
    except PipelineNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Query failed")
        raise HTTPException(
            status_code=500, detail="Internal error while processing query"
        ) from exc

    response_payload = dict(result)
    response_payload["request_id"] = response_payload.get("request_id") or request_id

    session_id = (payload.session_id or "").strip()
    if session_id and context_service is not None:
        try:
            context_service.add_interaction(
                InteractionRecord(
                    timestamp=request_started,
                    session_id=session_id,
                    user_id=payload.user_id,
                    question=question,
                    answer=str(response_payload.get("answer", "")),
                    grounded=bool(response_payload.get("grounded", False)),
                    failure_type=response_payload.get("failure_type"),
                    sources_count=len(response_payload.get("sources", [])),
                    latency_ms=int(response_payload.get("latency_ms", 0)),
                )
            )
        except Exception:
            logger.warning("Failed to store context interaction", exc_info=True)

    if interaction_log_service is not None:
        try:
            interaction_log_service.log_request(
                LoggedRequest(
                    request_id=str(response_payload["request_id"]),
                    timestamp=request_started,
                    route="/api/query",
                    session_id=session_id or None,
                    user_id=payload.user_id,
                    question=question,
                    answer=str(response_payload.get("answer", "")),
                    grounded=bool(response_payload.get("grounded", False)),
                    failure_type=response_payload.get("failure_type"),
                    latency_ms=int(response_payload.get("latency_ms", 0)),
                    wall_ms=int(response_payload.get("wall_ms", 0)),
                    intent=str(response_payload.get("intent", "")),
                    sources_count=len(response_payload.get("sources", [])),
                )
            )
        except Exception:
            logger.warning("Failed to append interaction log", exc_info=True)

    return QueryResponse(**response_payload)


@router.post(
    "/dispatch",
    response_model=DispatchResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def dispatch(payload: DispatchRequest, request: Request) -> DispatchResponse:
    settings = get_settings()
    capability_router = _capability_router(request)
    rag_service = _rag_service(request)
    trading_service = _trading_service(request)
    agent_service = _agent_service(request)

    question = payload.question.strip()
    if not question:
        raise HTTPException(status_code=400, detail="Question is empty")
    if len(question) > settings.max_question_length:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Question exceeds max length "
                f"({settings.max_question_length} chars)"
            ),
        )

    route = capability_router.route(question)

    try:
        if route.capability == Capability.RAG:
            result = await rag_service.query(question)
            return DispatchResponse(
                capability="rag",
                data=dict(result),
            )
        elif route.capability == Capability.TRADING:
            result = trading_service.analyze(question=question)
            return DispatchResponse(
                capability="trading",
                data={
                    "intent": result.intent,
                    "market": result.market,
                    "asset": result.asset,
                    "timeframe": result.timeframe,
                    "prompt": result.prompt,
                    "status": result.status,
                },
            )
        elif route.capability == Capability.AGENT:
            result = agent_service.analyze(question=question)
            return DispatchResponse(
                capability="agent",
                data={
                    "intent": result.intent,
                    "prompt": result.prompt,
                    "summary": result.summary,
                    "suggested_tools": result.suggested_tools,
                    "status": result.status,
                },
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=f"Capability {route.capability} not supported",
            )
    except PipelineNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Dispatch failed")
        raise HTTPException(
            status_code=500, detail="Internal error while processing request"
        ) from exc
