"""Jotform Agent webhook ingestion service.

Normalizes Jotform AI Agent conversation payloads into structured leads
and stores them as RAG memory for searchable retrieval.
"""

from __future__ import annotations

import json
import logging
import os
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import psycopg2
from psycopg2.extras import Json

logger = logging.getLogger(__name__)


@dataclass
class JotformLead:
    """Normalized Jotform lead data."""
    lead_id: str
    form_id: str
    submission_id: str
    source: str = "jotform"
    name: str = ""
    email: str = ""
    phone: str = ""
    company: str = ""
    service: str = ""
    location: str = ""
    urgency: str = ""
    message: str = ""
    intent: str = "general"
    raw_payload: dict[str, Any] | None = None
    created_at: datetime | None = None


def normalize_jotform_payload(payload: dict[str, Any]) -> JotformLead:
    """Normalize Jotform webhook payload into JotformLead.

    Extracts and maps common Jotform field names to standard schema.
    Handles missing fields gracefully with empty strings.

    Args:
        payload: Raw Jotform webhook JSON payload.

    Returns:
        Normalized JotformLead with intent classification.
    """
    # Generate IDs
    lead_id = str(uuid.uuid4())
    form_id = str(payload.get("formID", payload.get("form_id", "")))
    submission_id = str(payload.get("submissionID", payload.get("submission_id", "")))

    # Extract common field variations
    name = (
        payload.get("name") or
        payload.get("visitor_name") or
        payload.get("fullName") or
        payload.get("full_name") or
        ""
    )

    email = (
        payload.get("email") or
        payload.get("visitor_email") or
        payload.get("Email") or
        ""
    )

    phone = (
        payload.get("phone") or
        payload.get("visitor_phone") or
        payload.get("Phone") or
        payload.get("phoneNumber") or
        ""
    )

    company = (
        payload.get("company") or
        payload.get("company_name") or
        payload.get("visitor_company") or
        ""
    )

    service = (
        payload.get("service") or
        payload.get("services_required") or
        payload.get("services_enquired") or
        ""
    )

    location = (
        payload.get("location") or
        payload.get("city") or
        payload.get("address") or
        ""
    )

    urgency = (
        payload.get("urgency") or
        payload.get("priority") or
        ""
    )

    message = (
        payload.get("message") or
        payload.get("comments") or
        payload.get("conversation_summary") or
        payload.get("question") or
        ""
    )

    # Classify intent based on service/message content
    intent = _classify_intent(service, message)

    return JotformLead(
        lead_id=lead_id,
        form_id=form_id,
        submission_id=submission_id,
        source="jotform",
        name=str(name),
        email=str(email),
        phone=str(phone),
        company=str(company),
        service=str(service),
        location=str(location),
        urgency=str(urgency),
        message=str(message),
        intent=intent,
        raw_payload=payload,
        created_at=datetime.now(timezone.utc),
    )


def _classify_intent(service: str, message: str) -> str:
    """Classify lead intent based on service/message content.

    Rules:
    - eco: waste, wastewater, grease, municipality, environmental
    - cv: cv, resume, job, career, deliveroo
    - general: fallback

    Args:
        service: Service field text.
        message: Message field text.

    Returns:
        Intent classification: "eco", "cv", or "general".
    """
    combined = f"{service} {message}".lower()

    eco_keywords = ["waste", "wastewater", "grease", "municipality", "environmental"]
    cv_keywords = ["cv", "resume", "job", "career", "deliveroo"]

    if any(keyword in combined for keyword in eco_keywords):
        return "eco"
    if any(keyword in combined for keyword in cv_keywords):
        return "cv"
    return "general"


def format_jotform_memory(lead: JotformLead) -> str:
    """Format Jotform lead as RAG memory text.

    Creates structured text representation for embedding and retrieval.

    Args:
        lead: Normalized JotformLead.

    Returns:
        Formatted memory text string.
    """
    # Create raw summary from payload if available
    raw_summary = ""
    if lead.raw_payload:
        # Extract key fields for summary
        summary_parts = []
        for key in ["name", "email", "phone", "company", "service", "message"]:
            if key in lead.raw_payload:
                summary_parts.append(f"{key}: {lead.raw_payload[key]}")
        raw_summary = " | ".join(summary_parts) if summary_parts else str(lead.raw_payload)

    lines = [
        "[Jotform Lead]",
        f"Name: {lead.name}",
        f"Email: {lead.email}",
        f"Phone: {lead.phone}",
        f"Company: {lead.company}",
        f"Service: {lead.service}",
        f"Location: {lead.location}",
        f"Urgency: {lead.urgency}",
        f"Intent: {lead.intent}",
        f"Message: {lead.message}",
        f"Raw summary: {raw_summary}",
    ]
    return "\n".join(lines)


def save_jotform_lead(lead: JotformLead) -> None:
    """Save Jotform lead to PostgreSQL database.

    Inserts into agent_conversations table with link to leads table.
    Uses existing schema from init_db.sql.

    Args:
        lead: Normalized JotformLead to save.

    Raises:
        RuntimeError: If DATABASE_URL not configured.
        psycopg2.Error: If database operation fails.
    """
    database_url = os.environ.get("DATABASE_URL")
    if not database_url:
        raise RuntimeError("DATABASE_URL environment variable is required")

    with psycopg2.connect(database_url) as conn:
        with conn.cursor() as cur:
            # Insert into leads table
            cur.execute(
                """
                INSERT INTO leads (full_name, company_name, email, phone, services_required, source, status)
                VALUES (%s, %s, %s, %s, %s, %s, %s)
                RETURNING id
                """,
                (
                    lead.name or "Unknown",
                    lead.company or "Unknown",
                    lead.email or None,
                    lead.phone or None,
                    [lead.service] if lead.service else [],
                    lead.source,
                    "new",
                ),
            )
            lead_db_id = cur.fetchone()[0]

            # Insert into agent_conversations table
            cur.execute(
                """
                INSERT INTO agent_conversations (
                    session_id, visitor_name, visitor_company, visitor_email, visitor_phone,
                    services_enquired, conversation_summary, lead_captured, lead_id,
                    jotform_agent_id, started_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    lead.lead_id,  # Use lead_id as session_id
                    lead.name or None,
                    lead.company or None,
                    lead.email or None,
                    lead.phone or None,
                    [lead.service] if lead.service else [],
                    lead.message or None,
                    True,
                    lead_db_id,
                    lead.submission_id,  # Use submission_id as jotform_agent_id
                    lead.created_at or datetime.now(timezone.utc),
                ),
            )

            # Insert into form_submissions table for raw payload
            cur.execute(
                """
                INSERT INTO form_submissions (lead_id, provider, external_submission_id, raw_payload)
                VALUES (%s, %s, %s, %s)
                """,
                (
                    lead_db_id,
                    "jotform",
                    lead.lead_id,  # Use lead_id as external_submission_id
                    Json(lead.raw_payload) if lead.raw_payload else Json({}),
                ),
            )

    logger.info("Saved Jotform lead %s to database (lead_id=%s, db_id=%s)", lead.lead_id, lead.lead_id, lead_db_id)


def save_jotform_memory(lead: JotformLead, memory_dir: Path) -> Path:
    """Save Jotform lead as RAG memory file for index rebuild.

    Stores formatted memory text to file system for later ingestion
    into FAISS index via pipeline rebuild.

    Args:
        lead: Normalized JotformLead.
        memory_dir: Directory to store memory files.

    Returns:
        Path to created memory file.
    """
    memory_dir.mkdir(parents=True, exist_ok=True)
    memory_text = format_jotform_memory(lead)
    file_path = memory_dir / f"{lead.lead_id}.txt"
    file_path.write_text(memory_text, encoding="utf-8")
    logger.info("Saved Jotform memory to %s", file_path)
    return file_path


def ingest_jotform_payload(payload: dict[str, Any], memory_dir: Path | None = None) -> JotformLead:
    """Ingest Jotform webhook payload end-to-end.

    Normalizes payload, saves to database, and stores as RAG memory.

    Args:
        payload: Raw Jotform webhook JSON payload.
        memory_dir: Optional directory for memory files. If None, uses
                     JOTFORM_MEMORY_DIR env var or default.

    Returns:
        Ingested JotformLead.

    Raises:
        ValueError: If payload is empty or invalid.
        RuntimeError: If database or file storage fails.
    """
    if not payload or not isinstance(payload, dict):
        raise ValueError("Payload must be a non-empty dictionary")

    # Normalize
    lead = normalize_jotform_payload(payload)

    # Save to database
    try:
        save_jotform_lead(lead)
    except Exception as e:
        logger.error("Failed to save lead to database: %s", e)
        raise RuntimeError(f"Database save failed: {e}") from e

    # Save as RAG memory
    if memory_dir is None:
        memory_dir = Path(os.environ.get("JOTFORM_MEMORY_DIR", "data/jotform_memory"))

    try:
        save_jotform_memory(lead, memory_dir)
    except Exception as e:
        logger.error("Failed to save memory file: %s", e)
        # Don't fail the entire ingestion if memory file save fails
        # Database save is the critical part

    return lead
