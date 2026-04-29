"""Admin API routes.

Adds the following endpoints consumed by the admin dashboard:

- GET  /api/health     -- lightweight health probe
- GET  /admin/stats    -- system-wide statistics + monitoring
- GET  /leads          -- all leads (most recent first)
- GET  /leads/hot      -- hot leads only
- GET  /leads/failures -- queries that hit retrieval_miss or other failures
- GET  /leads/flagged  -- manually flagged bad answers
- POST /leads/{id}/flag -- toggle flag on a lead
- POST /leads/{id}/rerun -- re-dispatch a lead's query
- GET  /admin/monitoring -- aggregate latency / failure stats
- POST /api/dispatch   -- forward a query through the RAG pipeline
"""

from __future__ import annotations

import logging
import os
import secrets
import time
from typing import Any, Dict

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from fastapi.responses import HTMLResponse

from .services.leads_store import get_leads_store

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------
ADMIN_TOKEN = os.getenv("ADMIN_TOKEN", "")


def _generate_default_token() -> str:
    """Return a random token when none is configured (dev convenience)."""
    token = secrets.token_urlsafe(32)
    logger.warning(
        "No ADMIN_TOKEN configured -- generated ephemeral token: %s", token
    )
    return token


if not ADMIN_TOKEN:
    ADMIN_TOKEN = _generate_default_token()


async def verify_admin_token(
    x_admin_token: str = Header(default=""),
) -> None:
    """Dependency that rejects requests missing a valid admin token.

    The dashboard page itself injects the token from the login form into
    every fetch() call via the ``X-Admin-Token`` header.
    """
    if not secrets.compare_digest(x_admin_token, ADMIN_TOKEN):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin token",
        )


# ---------------------------------------------------------------------------
# Lead temperature classification
# ---------------------------------------------------------------------------

_HOT_INTENTS = {"eco", "cv"}
_WARM_CONFIDENCE_THRESHOLD = 0.65


def classify_lead_temperature(intent: str, confidence: float) -> str:
    """Derive hot / warm / cold from intent + confidence."""
    if intent in _HOT_INTENTS and confidence >= _WARM_CONFIDENCE_THRESHOLD:
        return "hot"
    if confidence >= _WARM_CONFIDENCE_THRESHOLD:
        return "warm"
    return "cold"


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def register_admin_routes(app: FastAPI) -> None:
    """Attach admin endpoints to *app*."""

    from pathlib import Path
    _STATIC_DIR = Path(__file__).resolve().parent.parent.parent / "static"

    # ---- Dashboard page (HTML) -----------------------------------------

    @app.get("/admin", include_in_schema=False)
    async def admin_page() -> HTMLResponse:
        html_path = _STATIC_DIR / "admin.html"
        if not html_path.exists():
            raise HTTPException(status_code=404, detail="Dashboard not found")
        return HTMLResponse(content=html_path.read_text(encoding="utf-8"))

    # ---- API health (lightweight) --------------------------------------

    @app.get("/api/health")
    async def api_health(request: Request) -> Dict[str, Any]:
        rag_ready = False
        index_count = 0
        if hasattr(request.app.state, "rag_service") and request.app.state.rag_service:
            rag_ready = request.app.state.rag_service.ready
            index_count = request.app.state.rag_service.index_count
        return {
            "status": "ok",
            "rag_ready": rag_ready,
            "index_count": index_count,
            "timestamp": time.time(),
        }

    # ---- System health (used by the original /health) ------------------

    @app.get("/health")
    async def health_check(request: Request) -> Dict[str, Any]:
        rag_ready = False
        index_count = 0
        if hasattr(request.app.state, "rag_service") and request.app.state.rag_service:
            rag_ready = request.app.state.rag_service.ready
            index_count = request.app.state.rag_service.index_count
        from .core.config import get_settings
        settings = get_settings()
        return {
            "status": "ok",
            "pipeline_ready": rag_ready,
            "version": settings.version,
            "chat_model": settings.chat_model,
            "index_count": index_count,
        }

    # ---- Admin stats (protected) ---------------------------------------

    @app.get("/admin/stats", dependencies=[Depends(verify_admin_token)])
    async def admin_stats(request: Request) -> Dict[str, Any]:
        store = get_leads_store()
        counts = store.counts_by_temperature()
        total = store.total_count()

        rag_ready = False
        index_count = 0
        if hasattr(request.app.state, "rag_service") and request.app.state.rag_service:
            rag_ready = request.app.state.rag_service.ready
            index_count = request.app.state.rag_service.index_count

        from .core.config import get_settings
        settings = get_settings()

        monitoring = store.monitoring_stats()

        return {
            "system": {
                "status": "ok",
                "version": settings.version,
                "chat_model": settings.chat_model,
                "rag_ready": rag_ready,
                "index_count": index_count,
            },
            "leads": {
                "total": total,
                "hot": counts.get("hot", 0),
                "warm": counts.get("warm", 0),
                "cold": counts.get("cold", 0),
            },
            "monitoring": monitoring,
        }

    # ---- Monitoring (protected) ----------------------------------------

    @app.get("/admin/monitoring", dependencies=[Depends(verify_admin_token)])
    async def admin_monitoring() -> Dict[str, Any]:
        store = get_leads_store()
        return store.monitoring_stats()

    # ---- Leads (protected) ---------------------------------------------

    @app.get("/leads", dependencies=[Depends(verify_admin_token)])
    async def list_leads() -> Dict[str, Any]:
        store = get_leads_store()
        leads = store.list_all(limit=200)
        return {"leads": leads, "total": store.total_count()}

    @app.get("/leads/hot", dependencies=[Depends(verify_admin_token)])
    async def list_hot_leads() -> Dict[str, Any]:
        store = get_leads_store()
        leads = store.list_by_temperature("hot", limit=200)
        return {"leads": leads, "total": len(leads)}

    @app.get("/leads/failures", dependencies=[Depends(verify_admin_token)])
    async def list_failures() -> Dict[str, Any]:
        store = get_leads_store()
        leads = store.list_failures(limit=200)
        return {"leads": leads, "total": len(leads)}

    @app.get("/leads/flagged", dependencies=[Depends(verify_admin_token)])
    async def list_flagged() -> Dict[str, Any]:
        store = get_leads_store()
        leads = store.list_flagged(limit=200)
        return {"leads": leads, "total": len(leads)}

    # ---- Lead actions (protected) --------------------------------------

    @app.post("/leads/{lead_id}/flag", dependencies=[Depends(verify_admin_token)])
    async def toggle_flag(lead_id: int) -> Dict[str, Any]:
        store = get_leads_store()
        lead = store.get_by_id(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")
        new_state = not bool(lead.get("flagged", 0))
        store.flag(lead_id, flagged=new_state)
        return {"id": lead_id, "flagged": new_state}

    @app.post("/leads/{lead_id}/rerun", dependencies=[Depends(verify_admin_token)])
    async def rerun_query(lead_id: int, request: Request) -> Dict[str, Any]:
        store = get_leads_store()
        lead = store.get_by_id(lead_id)
        if lead is None:
            raise HTTPException(status_code=404, detail="Lead not found")

        rag_service = getattr(request.app.state, "rag_service", None)
        if rag_service is None or not rag_service.ready:
            raise HTTPException(
                status_code=503, detail="RAG pipeline not ready"
            )

        question = lead["query"]
        t0 = time.perf_counter()
        result = await rag_service.query(question)
        wall_ms = int((time.perf_counter() - t0) * 1000)

        intent = result.get("intent", "general")
        confidence = result.get("intent_confidence", 0.0)
        temperature = classify_lead_temperature(intent, confidence)
        failure_type = result.get("failure_type")
        answer = result.get("answer", "")

        new_id = store.capture(
            query=question,
            intent=intent,
            temperature=temperature,
            source="admin_rerun",
            channel="api",
            latency_ms=wall_ms,
            failure_type=failure_type,
            answer=answer,
            metadata={"dispatch_result": result, "rerun_of": lead_id},
        )

        return {
            "original_id": lead_id,
            "new_id": new_id,
            "capability": "rag",
            "kind": intent,
            "status": "ok",
            "payload": result,
        }

    # ---- Dispatch (protected) ------------------------------------------

    @app.post("/api/dispatch", dependencies=[Depends(verify_admin_token)])
    async def dispatch_query(request: Request) -> Dict[str, Any]:
        body = await request.json()
        question = (body.get("question") or body.get("query") or "").strip()
        if not question:
            raise HTTPException(status_code=422, detail="question is required")

        session_id = body.get("session_id")
        user_id = body.get("user_id")

        rag_service = getattr(request.app.state, "rag_service", None)
        if rag_service is None or not rag_service.ready:
            raise HTTPException(
                status_code=503, detail="RAG pipeline not ready"
            )

        t0 = time.perf_counter()
        result = await rag_service.query(question)
        wall_ms = int((time.perf_counter() - t0) * 1000)

        intent = result.get("intent", "general")
        confidence = result.get("intent_confidence", 0.0)
        temperature = classify_lead_temperature(intent, confidence)
        failure_type = result.get("failure_type")
        answer = result.get("answer", "")

        store = get_leads_store()
        store.capture(
            query=question,
            intent=intent,
            temperature=temperature,
            source="admin_dispatch",
            session_id=session_id,
            user_id=user_id,
            channel="api",
            latency_ms=wall_ms,
            failure_type=failure_type,
            answer=answer,
            metadata={"dispatch_result": result},
        )

        return {
            "capability": "rag",
            "kind": intent,
            "status": "ok",
            "request_id": result.get("request_id", ""),
            "payload": result,
        }
