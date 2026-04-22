from __future__ import annotations

import asyncio
import logging
import time
import uuid

from fastapi import APIRouter, HTTPException, Request, status

from ..core.config import get_settings
from ..schemas import (
    AgentAnalyzeRequest,
    AgentAnalyzeResponse,
    CreateTaskRequest,
    DispatchRequest,
    DispatchResponse,
    ErrorResponse,
    ExecuteTaskRequest,
    ExecuteTaskResponse,
    GeneralChatResponse,
    HealthResponse,
    QueryRequest,
    QueryResponse,
    ScheduleTaskRequest,
    ScheduleTaskResponse,
    SystemHealthResponse,
    TaskResponse,
    TradingAnalyzeRequest,
    TradingAnalyzeResponse,
    TradingRuntimeRequest,
    TradingRuntimeResponse,
)
from ..services.agent_executor import AgentExecutor
from ..services.agent_service import AgentService
from ..services.execution_guard import ExecutionGuard
from ..services.general_chat_service import GeneralChatService
from ..services.capability_router import Capability, CapabilityRouter
from ..services.context_service import ContextService, InteractionRecord
from ..services.health_guardian import HealthGuardian
from ..services.interaction_log_service import InteractionLogService, LoggedRequest
from ..services.rag_service import PipelineNotReadyError, RagService
from ..services.scheduler_service import SchedulerService
from ..services.task_store import TaskStore
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


def _task_store(request: Request) -> TaskStore:
    service: TaskStore | None = getattr(request.app.state, "task_store", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Task store not initialised",
        )
    return service


def _scheduler_service(request: Request) -> SchedulerService:
    service: SchedulerService | None = getattr(request.app.state, "scheduler_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Scheduler service not initialised",
        )
    return service


def _agent_executor(request: Request) -> AgentExecutor:
    service: AgentExecutor | None = getattr(request.app.state, "agent_executor", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Agent executor not initialised",
        )
    return service


def _execution_guard(request: Request) -> ExecutionGuard:
    service: ExecutionGuard | None = getattr(request.app.state, "execution_guard", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Execution guard not initialised",
        )
    return service


def _general_chat_service(request: Request) -> GeneralChatService:
    service: GeneralChatService | None = getattr(request.app.state, "general_chat_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="General chat service not initialised",
        )
    return service


def _trading_runtime_service(request: Request):
    service = getattr(request.app.state, "trading_runtime_service", None)
    if service is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Trading runtime service not initialised",
        )
    return service


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
    "/trading/runtime/dry-run",
    response_model=TradingRuntimeResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def trading_runtime_dry_run(
    payload: TradingRuntimeRequest,
    request: Request,
) -> TradingRuntimeResponse:
    settings = get_settings()
    runtime_service = _trading_runtime_service(request)

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
        result = await runtime_service.run_dry_analysis(
            question=question,
            session_id=payload.session_id,
            user_id=payload.user_id,
        )
    except Exception as exc:
        logger.exception("Trading runtime dry-run failed")
        raise HTTPException(
            status_code=500,
            detail="Internal error while processing trading runtime dry-run"
        ) from exc

    return TradingRuntimeResponse(
        capability="trading",
        intent="runtime_analysis",
        status="ok" if result.get("accepted") else "rejected",
        execution_mode=result.get("execution_mode", "dry_run"),
        market=result.get("market"),
        asset=result.get("asset"),
        timeframe=result.get("timeframe"),
        risk_approved=result.get("risk_approved", False),
        risk_summary=result.get("risk_reason"),
        execution_summary=result.get("execution_summary"),
        normalized_symbol=result.get("normalized_symbol"),
        warnings=result.get("warnings", []),
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
    general_chat_service = _general_chat_service(request)
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
    request_started = time.time()
    request_id = str(uuid.uuid4())
    session_id = (payload.session_id or "").strip()

    if route.capability == Capability.ADMIN:
        raise HTTPException(
            status_code=400,
            detail="Admin capability is not exposed on this endpoint.",
        )

    try:
        if route.capability == Capability.TRADING:
            result = trading_service.analyze(question)
            return DispatchResponse(
                capability="trading",
                kind="trading_analysis",
                status="ok",
                request_id=request_id,
                payload={
                    "capability": result.capability,
                    "intent": result.intent,
                    "market": result.market,
                    "asset": result.asset,
                    "timeframe": result.timeframe,
                    "prompt": result.prompt,
                    "status": result.status,
                },
            )

        if route.capability == Capability.AGENT:
            result = agent_service.analyze(question)
            return DispatchResponse(
                capability="agent",
                kind="agent_analysis",
                status="ok",
                request_id=request_id,
                payload={
                    "capability": result.capability,
                    "intent": result.intent,
                    "prompt": result.prompt,
                    "summary": result.summary,
                    "suggested_tools": result.suggested_tools,
                    "status": result.status,
                },
            )

        if route.capability == Capability.GENERAL:
            try:
                result = await general_chat_service.chat(question)
                if result.status != "ok":
                    raise HTTPException(status_code=500, detail=result.answer)
                return DispatchResponse(
                    capability="general",
                    kind="general_chat",
                    status="ok",
                    request_id=request_id,
                    payload={
                        "capability": result.capability,
                        "intent": result.intent,
                        "answer": result.answer,
                        "status": result.status,
                    },
                )
            except HTTPException:
                raise
            except Exception as exc:
                logger.exception("General chat failed")
                raise HTTPException(
                    status_code=500,
                    detail=f"General chat failed: {exc}",
                ) from exc

        result = await rag_service.query(question)
        response_payload = dict(result)
        response_payload["request_id"] = response_payload.get("request_id") or request_id

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
                logger.warning("Failed to store dispatch context interaction", exc_info=True)

        if interaction_log_service is not None:
            try:
                interaction_log_service.log_request(
                    LoggedRequest(
                        request_id=str(response_payload["request_id"]),
                        timestamp=request_started,
                        route="/api/dispatch",
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
                logger.warning("Failed to append dispatch interaction log", exc_info=True)

        return DispatchResponse(
            capability="rag",
            kind="rag_answer",
            status="ok",
            request_id=str(response_payload["request_id"]),
            payload=response_payload,
        )

    except PipelineNotReadyError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        logger.exception("Dispatch failed")
        raise HTTPException(
            status_code=500, detail="Internal error while dispatching request"
        ) from exc


@router.post(
    "/agent/tasks",
    response_model=TaskResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def create_agent_task(
    payload: CreateTaskRequest,
    request: Request,
) -> TaskResponse:
    task_store = _task_store(request)
    task_id = str(uuid.uuid4())
    task = task_store.create_task(
        task_id=task_id,
        title=payload.title.strip(),
        prompt=payload.prompt.strip(),
        intent=payload.intent.strip(),
        session_id=payload.session_id,
        user_id=payload.user_id,
    )
    return TaskResponse(
        task_id=task.task_id,
        title=task.title,
        prompt=task.prompt,
        intent=task.intent,
        status=task.status,
        session_id=task.session_id,
        user_id=task.user_id,
        created_at=task.created_at,
        updated_at=task.updated_at,
        error_message=task.error_message,
        last_run_started_at=task.last_run_started_at,
        last_run_finished_at=task.last_run_finished_at,
    )


@router.get(
    "/agent/tasks",
    response_model=list[TaskResponse],
    responses={503: {"model": ErrorResponse}},
)
async def list_agent_tasks(
    request: Request,
    session_id: str | None = None,
) -> list[TaskResponse]:
    task_store = _task_store(request)
    tasks = task_store.list_tasks(session_id=session_id)
    return [
        TaskResponse(
            task_id=task.task_id,
            title=task.title,
            prompt=task.prompt,
            intent=task.intent,
            status=task.status,
            session_id=task.session_id,
            user_id=task.user_id,
            created_at=task.created_at,
            updated_at=task.updated_at,
            error_message=task.error_message,
            last_run_started_at=task.last_run_started_at,
            last_run_finished_at=task.last_run_finished_at,
        )
        for task in tasks
    ]


@router.post(
    "/agent/tasks/schedule",
    response_model=ScheduleTaskResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def schedule_agent_task(
    payload: ScheduleTaskRequest,
    request: Request,
) -> ScheduleTaskResponse:
    task_store = _task_store(request)
    scheduler_service = _scheduler_service(request)

    task = task_store.get_task(payload.task_id)
    if task is None:
        raise HTTPException(status_code=400, detail="Task not found")

    try:
        updated = task_store.set_scheduled(payload.task_id)
        if updated is None:
            raise HTTPException(status_code=400, detail="Task not found")
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    scheduled = scheduler_service.schedule(payload.task_id, payload.run_at)

    return ScheduleTaskResponse(
        task_id=scheduled.task_id,
        run_at=scheduled.run_at,
        status=scheduled.status,
        created_at=scheduled.created_at,
    )


@router.post(
    "/agent/tasks/execute",
    response_model=ExecuteTaskResponse,
    responses={
        400: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
    },
)
async def execute_agent_task(
    payload: ExecuteTaskRequest,
    request: Request,
) -> ExecuteTaskResponse:
    task_store = _task_store(request)
    agent_executor = _agent_executor(request)
    execution_guard = _execution_guard(request)

    task = task_store.get_task(payload.task_id)
    if task is None:
        raise HTTPException(status_code=400, detail="Task not found")

    try:
        result = await asyncio.to_thread(
            execution_guard.run,
            task.task_id,
            lambda: agent_executor.execute(task.task_id, task.prompt),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=f"Task execution failed: {exc}",
        ) from exc

    return ExecuteTaskResponse(
        task_id=result.task_id,
        status=result.status,
        output=result.output,
        started_at=result.started_at,
        finished_at=result.finished_at,
    )
