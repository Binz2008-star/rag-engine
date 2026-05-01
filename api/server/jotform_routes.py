from __future__ import annotations

import logging
from typing import Any

from fastapi import HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class JotFormLeadRequest(BaseModel):
    idempotency_key: str
    raw_payload: dict[str, Any]


def register_jotform_routes(app) -> None:
    """Register JotForm integration routes."""

    @app.post("/api/jotform/lead")
    async def jotform_lead(req: JotFormLeadRequest, http_request: Request) -> dict[str, Any]:
        """
        Receive JotForm submission via n8n integration.
        This endpoint normalizes and stores the lead data.
        """
        logger.info(
            "Received JotForm lead: idempotency_key=%s",
            req.idempotency_key,
        )

        # TODO: Store in Neon database via integration_events table
        # For now, just acknowledge receipt
        return {
            "status": "received",
            "idempotency_key": req.idempotency_key,
            "message": "Lead received successfully",
        }
