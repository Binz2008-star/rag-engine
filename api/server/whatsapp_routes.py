"""WhatsApp webhook routes.

Handles inbound messages from Twilio (form-encoded) or generic JSON
webhooks, routes them through the RAG pipeline, and returns a reply.

Flow::

    WhatsApp user → Twilio → POST /api/webhooks/whatsapp
                                   ↓
                            RAG pipeline (internal)
                                   ↓
                            TwiML reply  ←  lead captured
"""

from __future__ import annotations

import logging
import re
import time
from typing import Any, Dict

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response

from .admin_routes import classify_lead_temperature
from .services.leads_store import get_leads_store

logger = logging.getLogger(__name__)

# Terms that signal buying intent — trigger a call-to-action.
_BUYING_INTENT_PATTERNS = re.compile(
    r"\b(price|pricing|cost|quote|quotation|aed|how much|size [a-d]|amc)\b",
    re.IGNORECASE,
)

_WHATSAPP_FALLBACK = (
    "I don't have enough information to answer that right now. "
    "Would you like to speak with our team? "
    "Reply with your name and we'll get back to you."
)

_CTA_SUFFIX = "\n\nWould you like a quotation or site visit? Reply *yes* to proceed."


def _format_whatsapp_reply(answer: str, query: str, failure_type: str | None) -> str:
    """Build a WhatsApp-friendly reply string."""
    if failure_type or not answer or answer.strip().lower() == "insufficient data.":
        return _WHATSAPP_FALLBACK

    reply = answer.strip()
    if _BUYING_INTENT_PATTERNS.search(query):
        reply += _CTA_SUFFIX
    return reply


def _twiml_response(text: str) -> Response:
    """Wrap *text* in a Twilio MessagingResponse XML envelope."""
    escaped = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response>"
        f"<Message>{escaped}</Message>"
        "</Response>"
    )
    return Response(content=xml, media_type="application/xml")


def register_whatsapp_routes(app: FastAPI) -> None:
    """Attach WhatsApp webhook endpoints to *app*."""

    @app.post("/api/webhooks/whatsapp")
    async def whatsapp_webhook(request: Request) -> Response:
        """Handle inbound WhatsApp messages via Twilio or generic JSON."""
        content_type = request.headers.get("content-type", "")

        if "application/x-www-form-urlencoded" in content_type:
            form = await request.form()
            message = str(form.get("Body", "")).strip()
            user_id = str(form.get("From", "")).strip()
            is_twilio = True
        else:
            body = await request.json()
            message = (body.get("message") or body.get("Body") or "").strip()
            user_id = (body.get("from") or body.get("From") or "").strip()
            is_twilio = False

        if not message:
            if is_twilio:
                return _twiml_response("Please send a message.")
            return Response(
                content='{"status":"ignored"}',
                media_type="application/json",
            )

        logger.info(
            "whatsapp: incoming user=%s msg=%r",
            user_id[:20] if user_id else "unknown",
            message[:80],
        )

        rag_service = getattr(request.app.state, "rag_service", None)
        if rag_service is None or not rag_service.ready:
            reply = _WHATSAPP_FALLBACK
            _capture_lead(
                query=message,
                user_id=user_id,
                reply=reply,
                failure_type="rag_unavailable",
            )
            if is_twilio:
                return _twiml_response(reply)
            return _json_reply(reply)

        t0 = time.perf_counter()
        try:
            result = await rag_service.query(message)
        except Exception:
            logger.exception("whatsapp: pipeline error for %r", message[:80])
            reply = _WHATSAPP_FALLBACK
            _capture_lead(
                query=message,
                user_id=user_id,
                reply=reply,
                failure_type="pipeline_error",
            )
            if is_twilio:
                return _twiml_response(reply)
            return _json_reply(reply)

        wall_ms = int((time.perf_counter() - t0) * 1000)
        intent = result.get("intent", "general")
        confidence = result.get("intent_confidence", 0.0)
        failure_type = result.get("failure_type")
        answer = result.get("answer", "")

        reply = _format_whatsapp_reply(answer, message, failure_type)

        _capture_lead(
            query=message,
            user_id=user_id,
            reply=reply,
            intent=intent,
            confidence=confidence,
            failure_type=failure_type,
            latency_ms=wall_ms,
            metadata={"dispatch_result": result},
        )

        logger.info(
            "whatsapp: reply user=%s intent=%s failure=%s latency=%dms",
            user_id[:20] if user_id else "unknown",
            intent,
            failure_type,
            wall_ms,
        )

        if is_twilio:
            return _twiml_response(reply)
        return _json_reply(reply)

    @app.get("/api/webhooks/whatsapp")
    async def whatsapp_verify(request: Request) -> Response:
        """Handle Twilio / Meta webhook verification (GET)."""
        challenge = request.query_params.get("hub.challenge", "ok")
        return Response(content=str(challenge), media_type="text/plain")


def _capture_lead(
    *,
    query: str,
    user_id: str,
    reply: str,
    intent: str = "general",
    confidence: float = 0.0,
    failure_type: str | None = None,
    latency_ms: int | None = None,
    metadata: Dict[str, Any] | None = None,
) -> None:
    """Store a WhatsApp interaction as a lead."""
    temperature = classify_lead_temperature(intent, confidence)
    store = get_leads_store()
    store.capture(
        query=query,
        intent=intent,
        temperature=temperature,
        source="whatsapp",
        user_id=user_id,
        channel="whatsapp",
        latency_ms=latency_ms,
        failure_type=failure_type,
        answer=reply,
        metadata=metadata,
    )


def _json_reply(text: str) -> Response:
    import json
    return Response(
        content=json.dumps({"reply": text}),
        media_type="application/json",
    )
