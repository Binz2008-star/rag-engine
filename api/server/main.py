from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from .api.routes import router as api_router  # noqa: E402
from .core.config import get_settings  # noqa: E402
from .core.logging import configure_logging  # noqa: E402
from .infra.ollama_health import OllamaUnavailableError, check_ollama  # noqa: E402
from .services.agent_service import AgentService  # noqa: E402
from .services.capability_router import CapabilityRouter  # noqa: E402
from .services.context_service import ContextService  # noqa: E402
from .services.health_guardian import HealthGuardian  # noqa: E402
from .services.interaction_log_service import InteractionLogService  # noqa: E402
from .services.rag_service import RagService  # noqa: E402
from .services.trading_service import TradingService  # noqa: E402

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    configure_logging(settings.log_level)

    logger.info(
        "Starting %s v%s on %s:%d",
        settings.app_name,
        settings.version,
        settings.host,
        settings.port,
    )

    app.state.context_service = ContextService()
    app.state.interaction_log_service = InteractionLogService()
    app.state.capability_router = CapabilityRouter()
    app.state.health_guardian = HealthGuardian()
    app.state.trading_service = TradingService()
    app.state.agent_service = AgentService()

    try:
        await check_ollama(
            base_url=settings.ollama_base_url,
            required_models=settings.ollama_required_models,
        )
        logger.info("Ollama health check passed")
    except OllamaUnavailableError as exc:
        logger.error("Ollama health check failed: %s", exc)
        raise SystemExit(1) from exc

    service = RagService(index_dir=settings.index_dir)
    app.state.rag_service = service

    try:
        await service.startup()
    except Exception:
        logger.exception("Pipeline startup failed - API will report degraded")

    try:
        yield
    finally:
        logger.info("Shutting down RAG service")
        await service.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        version=settings.version,
        lifespan=lifespan,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins or ["http://localhost:3000", "http://localhost:3001"],
        allow_credentials=True,
        allow_methods=["GET", "POST", "OPTIONS"],
        allow_headers=["*"],
    )

    app.include_router(api_router)

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.app_name,
            "version": settings.version,
            "docs": "/docs",
            "health": "/api/health",
        }

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        request: Request, exc: StarletteHTTPException
    ) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": exc.__class__.__name__, "detail": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            content={"error": "ValidationError", "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        request: Request, exc: Exception
    ) -> JSONResponse:
        logger.exception(
            "Unhandled exception on %s %s", request.method, request.url.path
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={"error": "InternalServerError", "detail": "Unexpected error"},
        )

    return app


app = create_app()
