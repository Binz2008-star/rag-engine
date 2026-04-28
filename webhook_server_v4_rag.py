"""
ECO Technology — Lead Automation Pipeline v4.0
===============================================
Production-grade FastAPI webhook server with RAG integration.

Changes vs v3.0:
  ✅ Hard RAG routing for INT-02, INT-03, INT-09, INT-18 (service/compliance/company/documentation)
  ✅ RAG health check and graceful timeout handling
  ✅ RAG failures do not block lead capture
  ✅ RAG usage logging (intent, question, success/failure, latency)
  ✅ Secrets moved to .env configuration
  ✅ Async email dispatch via BackgroundTasks (no blocking)
  ✅ Idempotency: duplicate webhook submissions are silently skipped
  ✅ Retry system: tenacity with 3 attempts + exponential backoff
  ✅ Lead state tracking: email_status column updated after dispatch
  ✅ Event log: every action written to lead_events table
  ✅ Failure logging: failed emails recorded as events, never silently dropped

Endpoints:
  POST /webhook/jotform        — Jotform form submissions
  POST /webhook/agent          — Robin AI agent lead captures with RAG routing
  GET  /leads                  — Quick lead dashboard
  GET  /leads/{id}/events      — Full event timeline for a lead
  GET  /health                 — Health check
  GET  /rag/health             — RAG service health check
"""

import os
import json
import smtplib
import logging
import hashlib
import time
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timezone
from typing import Optional
from dotenv import load_dotenv

load_dotenv()

import psycopg2
import psycopg2.extras
from fastapi import FastAPI, Request, BackgroundTasks, HTTPException, Header, Depends
from fastapi.responses import JSONResponse
from fastapi.security import APIKeyHeader
from tenacity import retry, stop_after_attempt, wait_exponential, RetryError

# RAG client import
try:
    from rag_client import RAGClient, get_rag_client
    RAG_AVAILABLE = True
except ImportError:
    RAG_AVAILABLE = False
    logging.warning("RAG client not available - RAG routing disabled")

# Phase 2 imports
try:
    from lead_scorer import get_scorer
    from rag_client_webhook import rag_health as rag_backend_health
    SCORING_AVAILABLE = True
except ImportError:
    SCORING_AVAILABLE = False
    logging.warning("Lead scorer not available - scoring disabled")

# ─── Config (from .env) ───────────────────────────────────────────────────────
# Critical: All secrets must be in .env - no fallbacks in source code
DB_URL = os.environ["DATABASE_URL"]
INTERNAL_EMAIL     = os.environ.get("NOTIFY_EMAIL", "robenedwan@gmail.com")
COMPANY_NAME       = "ECO Technology Environmental Protection Services LLC"
COMPANY_PHONE      = "+971 52 223 3989"
WEBSITE            = os.environ.get("WEBSITE", "https://binz2008-star.github.io/eco-environmental-uae")
GMAIL_USER         = os.environ.get("GMAIL_USER", "robenedwan@gmail.com")
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")  # MUST be set via .env

# RAG configuration
RAG_SERVICE_URL = os.environ.get("RAG_SERVICE_URL", "http://localhost:8001")
RAG_ENABLED = os.environ.get("RAG_ENABLED", "true").lower() == "true"
RAG_TIMEOUT = 15.0  # seconds
RAG_HEALTHY = False  # State variable to track RAG service health

# Environment mode
ENV_MODE = os.environ.get("ENV", "production").lower()

# Database validation (can be skipped for testing)
SKIP_DB_VALIDATION = os.environ.get("SKIP_DB_VALIDATION", "false").lower() == "true"

# API authentication
API_KEY = os.environ.get("API_KEY", "")  # Required for webhook/admin endpoints in production

# Email configuration
EMAIL_ENABLED = bool(GMAIL_USER and GMAIL_APP_PASSWORD)
GMAIL_APP_PASSWORD = GMAIL_APP_PASSWORD.replace(" ", "") if GMAIL_APP_PASSWORD else ""

# Intents that should route to RAG
RAG_INTENTS = {"INT-02", "INT-03", "INT-09", "INT-18"}

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
log = logging.getLogger(__name__)

app = FastAPI(title="ECO Technology Lead Pipeline", version="4.0")

# API key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def verify_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key for protected endpoints."""
    if ENV_MODE == "development":
        # Allow access in development mode without API key
        return True

    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY not configured. Set API_KEY environment variable in production."
        )
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

async def verify_webhook_api_key(api_key: str = Depends(api_key_header)):
    """Verify API key for webhook endpoints (Jotform/Agent)."""
    if ENV_MODE == "development":
        # Allow access in development mode without API key
        return True

    if not API_KEY:
        raise HTTPException(
            status_code=500,
            detail="API_KEY not configured. Set API_KEY environment variable in production."
        )
    if not api_key:
        raise HTTPException(status_code=401, detail="API key required for webhooks")
    if api_key != API_KEY:
        raise HTTPException(status_code=403, detail="Invalid API key")
    return True

@app.on_event("startup")
async def startup_event():
    """Start background scheduler on server startup."""
    global RAG_HEALTHY

    try:
        from scheduler import start_scheduler
        start_scheduler()
        log.info("Scheduler active — daily report 7AM UAE, touch check every 6h")
    except Exception as e:
        log.warning(f"Scheduler failed to start: {e}")

    # Check RAG service health on startup
    if RAG_ENABLED and RAG_AVAILABLE:
        try:
            rag_client = get_rag_client()
            is_healthy = await rag_client.health_check()
            RAG_HEALTHY = is_healthy
            if is_healthy:
                log.info(f"RAG service healthy at {RAG_SERVICE_URL}")
            else:
                log.warning(f"RAG service unhealthy at {RAG_SERVICE_URL} - RAG routing disabled")
        except Exception as e:
            RAG_HEALTHY = False
            log.warning(f"RAG health check failed: {e} - RAG routing disabled")

    # Validate email credentials
    if not GMAIL_APP_PASSWORD:
        log.warning("GMAIL_APP_PASSWORD not set - email dispatch disabled")
    else:
        log.info("Email credentials validated")

    # Validate database schema (skip if SKIP_DB_VALIDATION is set)
    if not SKIP_DB_VALIDATION:
        try:
            conn = get_db()
            cur = conn.cursor()

            # Check for required tables
            cur.execute("""
                SELECT table_name FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('leads', 'lead_events', 'agent_conversations', 'form_submissions')
            """)
            existing_tables = {row['table_name'] for row in cur.fetchall()}

            required_tables = {'leads', 'lead_events', 'agent_conversations', 'form_submissions'}
            missing_tables = required_tables - existing_tables

            if missing_tables:
                log.error(f"Missing required database tables: {missing_tables}")
                log.error("Run database migrations before starting the server")
                raise RuntimeError(f"Missing database tables: {missing_tables}")

            # Check for required columns in leads table
            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_name = 'leads' AND table_schema = 'public'
                AND column_name IN ('email_status', 'source', 'services_required')
            """)
            existing_columns = {row['column_name'] for row in cur.fetchall()}

            required_columns = {'email_status', 'source', 'services_required'}
            missing_columns = required_columns - existing_columns

            if missing_columns:
                log.error(f"Missing required columns in leads table: {missing_columns}")
                log.error("Run database migrations before starting the server")
                raise RuntimeError(f"Missing database columns: {missing_columns}")

            cur.close()
            conn.close()
            log.info("Database schema validated")

        except Exception as e:
            log.error(f"Database schema validation failed: {e}")
            log.error("Run database migrations before starting the server")
            raise
    else:
        log.warning("Database schema validation skipped (SKIP_DB_VALIDATION=true)")


# ─── RAG Routing Logic ─────────────────────────────────────────────────────────
def should_route_to_rag(intent: str, message: str) -> bool:
    """Determine if a query should route to RAG based on intent and content."""
    if not RAG_ENABLED or not RAG_AVAILABLE or not RAG_HEALTHY:
        return False

    if intent in RAG_INTENTS:
        return True

    # Fallback: check for service/compliance keywords with ECO context
    # Narrowed to avoid false positives on generic words like "offer", "provide"
    service_keywords = [
        "grease trap", "sewage", "jetting", "desludging",
        "compliance", "regulation", "permit", "certification",
        "iso", "municipality", "approved", "environmental",
        "waste management", "biological treatment", "uco recycling",
        "confined space", "amc", "maintenance contract"
    ]

    # Require ECO context for generic keywords
    generic_keywords = ["service", "offer", "provide", "handle", "manage"]
    eco_context = ["eco", "technology", "environmental", "protection"]

    message_lower = message.lower()

    # Check specific service keywords
    if any(keyword in message_lower for keyword in service_keywords):
        return True

    # Check generic keywords only with ECO context
    if any(keyword in message_lower for keyword in generic_keywords):
        return any(context in message_lower for context in eco_context)

    return False


async def query_rag_safely(query: str, intent: str, caller: str = "webhook_server") -> dict:
    """
    Query RAG service with safeguards using async HTTP client.

    Returns dict with keys: answer, success, latency, error (if any)
    """
    if not RAG_ENABLED or not RAG_AVAILABLE or not RAG_HEALTHY:
        return {
            "answer": None,
            "success": False,
            "latency": 0.0,
            "error": "RAG disabled or unavailable"
        }

    start_time = time.time()

    try:
        import httpx
        async with httpx.AsyncClient(timeout=RAG_TIMEOUT) as client:
            response = await client.post(
                f"{RAG_SERVICE_URL}/query",
                json={"query": query},
                timeout=RAG_TIMEOUT
            )
            response.raise_for_status()
            result = response.json()

        elapsed = time.time() - start_time

        # Log RAG usage
        log.info(
            f"[RAG] Query | intent={intent} | success={result.get('answer') is not None} | "
            f"latency={elapsed:.3f}s | sources={len(result.get('sources', []))}"
        )

        return {
            "answer": result.get("answer"),
            "success": result.get("answer") is not None and result.get("answer") != "Insufficient data.",
            "latency": elapsed,
            "error": None,
            "sources": result.get("sources", []),
            "intent": result.get("intent"),
            "intent_confidence": result.get("intent_confidence"),
        }

    except Exception as e:
        elapsed = time.time() - start_time
        log.error(f"[RAG] Query failed: {e} | latency={elapsed:.3f}s")
        return {
            "answer": None,
            "success": False,
            "latency": elapsed,
            "error": str(e)
        }


def compose_sales_response_with_rag(rag_result: dict, intent: str) -> str:
    """
    Compose sales response incorporating RAG answer.

    This function bridges the RAG-grounded answer with Robin AI's sales voice.
    """
    rag_answer = rag_result.get("answer", "")
    if not rag_answer or rag_answer == "Insufficient data.":
        return None

    # Add Robin AI sales framing
    if intent == "INT-02":  # SERVICE_ENQUIRY
        response = f"Based on our documentation: {rag_answer}\n\n"
        response += "What's your facility type and which service do you need?"
    elif intent == "INT-03":  # COMPLIANCE_CONCERN
        response = f"Based on our compliance documentation: {rag_answer}\n\n"
        response += "I can arrange a free compliance audit. What's your property type and location?"
    elif intent == "INT-09":  # GENERAL_INFO
        response = f"Based on our records: {rag_answer}\n\n"
        response += "Would you like more specific information about any of our services?"
    elif intent == "INT-18":  # DOCUMENTATION_REQUEST
        response = f"Based on our documentation standards: {rag_answer}\n\n"
        response += "Would you like a sample documentation package sent to your email?"
    else:
        response = f"Based on our documentation: {rag_answer}"

    return response


# ─── DB helpers ────────────────────────────────────────────────────────────────
def get_db():
    return psycopg2.connect(DB_URL, cursor_factory=psycopg2.extras.RealDictCursor)


def log_event(lead_id: int, event_type: str, payload: dict):
    """Write an immutable event record to lead_events."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "INSERT INTO lead_events (lead_id, event_type, payload) VALUES (%s, %s, %s)",
            (lead_id, event_type, json.dumps(payload))
        )
        conn.commit()
    except Exception as e:
        log.error(f"log_event failed [{event_type}] lead={lead_id}: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def is_duplicate(idempotency_key: str) -> bool:
    """Return True if this idempotency_key has already been processed."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "SELECT 1 FROM form_submissions WHERE idempotency_key = %s LIMIT 1",
            (idempotency_key,)
        )
        return cur.fetchone() is not None
    finally:
        cur.close()
        conn.close()


def store_lead(data: dict) -> int:
    """Upsert lead by email. Returns lead_id."""
    # Ensure required fields have values
    if not data.get("name"):
        data["name"] = "Unknown"
    if not data.get("company"):
        data["company"] = "Unknown"

    conn = get_db()
    cur = conn.cursor()
    services_arr = [data["service"]] if data.get("service") else []
    try:
        cur.execute("SELECT id FROM leads WHERE email = %s", (data.get("email"),))
        existing = cur.fetchone()
        if existing:
            cur.execute(
                """UPDATE leads SET
                       full_name         = COALESCE(%s, full_name),
                       company_name      = COALESCE(%s, company_name),
                       phone             = COALESCE(%s, phone),
                       services_required = COALESCE(%s, services_required),
                       source            = COALESCE(%s, source),
                       updated_at        = NOW()
                   WHERE id = %s RETURNING id""",
                (data.get("name"), data.get("company"), data.get("phone"),
                 services_arr or None, data.get("source", "website_form"),
                 existing["id"])
            )
            lead_id = cur.fetchone()["id"]
        else:
            # Phase 2: Score the lead
            lead_score = None
            score_band = None
            rag_intent = None
            rag_confidence = None
            rag_method = None
            recommended_action = None

            if SCORING_AVAILABLE:
                try:
                    scorer = get_scorer()
                    # Get RAG classification if available
                    rag_result = None
                    if RAG_AVAILABLE and RAG_ENABLED:
                        try:
                            from rag_client_webhook import classify_lead
                            question = f"{data.get('company', '')} {services_arr} {data.get('message', '')}"
                            rag_result = classify_lead(question)
                            rag_intent = rag_result.get("intent")
                            rag_confidence = rag_result.get("confidence")
                            rag_method = rag_result.get("method")
                        except Exception as e:
                            log.warning(f"RAG classification failed: {e}")

                    # Score the lead
                    score_result = scorer.score(data, rag_result)
                    lead_score = score_result.get("lead_score")
                    score_band = score_result.get("score_band")
                    recommended_action = score_result.get("recommended_action")
                except Exception as e:
                    log.warning(f"Lead scoring failed: {e}")

            cur.execute(
                """INSERT INTO leads
                       (full_name, company_name, email, phone,
                        services_required, source, status, email_status,
                        lead_score, score_band, rag_intent, rag_confidence, rag_method,
                        recommended_action, scored_at,
                        created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, 'new', 'pending',
                           %s, %s, %s, %s, %s, %s,
                           CASE WHEN %s IS NOT NULL THEN NOW() ELSE NULL END,
                           NOW(), NOW())
                   RETURNING id""",
                (data.get("name"), data.get("company"), data.get("email"),
                 data.get("phone"), services_arr, data.get("source", "website_form"),
                 lead_score, score_band, rag_intent, rag_confidence, rag_method,
                 recommended_action, lead_score)
            )
            lead_id = cur.fetchone()["id"]
        conn.commit()
        return lead_id
    finally:
        cur.close()
        conn.close()


def store_form_submission(data: dict, lead_id: int, idempotency_key: str):
    """Log raw form submission. Silently skips on duplicate key."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO form_submissions
                   (lead_id, form_id, submission_data, idempotency_key, submitted_at)
               VALUES (%s, %s, %s, %s, NOW())
               ON CONFLICT (idempotency_key) DO NOTHING""",
            (lead_id, data.get("form_id", "unknown"),
             json.dumps(data), idempotency_key)
        )
        conn.commit()
    except Exception as e:
        log.error(f"store_form_submission failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


def update_email_status(lead_id: int, status: str):
    """Update leads.email_status for state tracking."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            "UPDATE leads SET email_status = %s WHERE id = %s",
            (status, lead_id)
        )
        conn.commit()
    except Exception as e:
        log.error(f"update_email_status failed: {e}")
        conn.rollback()
    finally:
        cur.close()
        conn.close()


# ─── Email layer ───────────────────────────────────────────────────────────────
@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=4, max=15),
    reraise=True
)
def _smtp_send(to: str, subject: str, body: str):
    """Low-level SMTP send. Retried up to 3x with exponential backoff."""
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"]    = f"Robin Edwan — ECO Technology <{GMAIL_USER}>"
    msg["To"]      = to
    msg.attach(MIMEText(body, "plain", "utf-8"))
    with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
        server.login(GMAIL_USER, GMAIL_APP_PASSWORD)
        server.sendmail(GMAIL_USER, [to], msg.as_string())


def send_client_thankyou(lead: dict) -> bool:
    name    = lead.get("name", "Valued Client")
    service = lead.get("service", "your requested service")
    email   = lead.get("email")
    if not email:
        return False
    subject = "شكراً لتواصلك مع ECO Technology | Thank You for Contacting Us"
    body = f"""Dear {name},

Thank you for reaching out to ECO Technology Environmental Protection Services LLC.
We have received your enquiry regarding: {service}

Our team will review your request and contact you within 2 business hours to discuss your requirements and arrange a free site visit.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
What happens next:
  1. Our specialist reviews your request
  2. We contact you within 2 hours to confirm details
  3. Free site visit arranged at your convenience
  4. Detailed quotation provided within 24 hours
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
For urgent matters (overflow, blockage, emergency):
📞 Call us directly: {COMPANY_PHONE}
🌐 {WEBSITE}

Best regards,
Robin Edwan — General Manager
{COMPANY_NAME}
📞 {COMPANY_PHONE} · Ajman, UAE · Est. 2016 · ISO 14001 · ISO 9001
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
شكراً لتواصلك مع شركة ECO Technology لخدمات الحماية البيئية.
لقد استلمنا طلبك وسيتواصل معك فريقنا خلال ساعتين.
للحالات الطارئة: {COMPANY_PHONE}
"""
    try:
        _smtp_send(email, subject, body)
        return True
    except RetryError as e:
        log.error(f"Client thank-you FAILED after 3 retries → {email}: {e}")
        return False


def send_internal_alert(lead: dict, lead_id: int, source: str) -> bool:
    name    = lead.get("name", "Unknown")
    company = lead.get("company", "Not provided")
    email   = lead.get("email", "Not provided")
    phone   = lead.get("phone", "Not provided")
    service = lead.get("service", "Not specified")
    ts      = datetime.now(timezone.utc).strftime("%d %b %Y, %H:%M UTC")
    subject = f"🔔 New Lead #{lead_id} — {name} ({company}) via {source}"
    body = f"""NEW LEAD CAPTURED — ECO Technology Pipeline
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Lead ID   : #{lead_id}
Source    : {source}
Received  : {ts}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Name      : {name}
Company   : {company}
Email     : {email}
Phone     : {phone}
Service   : {service}
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
ACTION: Contact {name} within 2 hours
→ Reply: {email}  |  Call: {phone}
"""
    try:
        _smtp_send(INTERNAL_EMAIL, subject, body)
        return True
    except RetryError as e:
        log.error(f"Internal alert FAILED after 3 retries → lead #{lead_id}: {e}")
        return False


# ─── Background task (runs AFTER response is returned to caller) ───────────────
def dispatch_emails(lead: dict, lead_id: int, source: str):
    """
    Async background task. Sends both emails, updates lead state, logs events.
    This function is NEVER called inside the request thread.
    """
    if not EMAIL_ENABLED:
        update_email_status(lead_id, "disabled")
        log_event(lead_id, "email_disabled", {
            "reason": "EMAIL_ENABLED=false or credentials missing",
            "source": source
        })
        log.warning(f"Email dispatch disabled for lead #{lead_id} - EMAIL_ENABLED={EMAIL_ENABLED}")
        return

    update_email_status(lead_id, "sending")

    client_sent   = send_client_thankyou(lead)
    internal_sent = send_internal_alert(lead, lead_id, source)

    if client_sent and internal_sent:
        final_status = "sent"
    elif client_sent or internal_sent:
        final_status = "partial"
    else:
        final_status = "failed"

    update_email_status(lead_id, final_status)

    log_event(lead_id, "email_client_thankyou", {
        "success": client_sent, "to": lead.get("email"), "source": source
    })
    log_event(lead_id, "email_internal_alert", {
        "success": internal_sent, "to": INTERNAL_EMAIL, "source": source
    })

    if final_status == "failed":
        log.error(f"Both emails failed for lead #{lead_id} — manual follow-up required")


# ─── Endpoints ─────────────────────────────────────────────────────────────────
@app.get("/health")
async def health():
    """Health check with RAG status."""
    rag_status = {"available": RAG_AVAILABLE, "enabled": RAG_ENABLED}
    if RAG_AVAILABLE and RAG_ENABLED:
        try:
            rag_health_result = rag_backend_health()
            rag_status["healthy"] = rag_health_result.get("healthy", False)
            rag_status["pipeline_ready"] = rag_health_result.get("pipeline_ready", False)
        except Exception as e:
            rag_status["healthy"] = False
            rag_status["error"] = str(e)

    return {
        "status": "ok",
        "version": "4.1",
        "phase": "2",
        "rag": rag_status,
        "scoring_available": SCORING_AVAILABLE,
    }


@app.get("/rag/health")
async def rag_health():
    """RAG service health check endpoint with state update."""
    global RAG_HEALTHY
    if not RAG_ENABLED or not RAG_AVAILABLE:
        return {"rag_healthy": False, "reason": "RAG disabled or client unavailable"}
    try:
        rag_client = get_rag_client()
        is_healthy = await rag_client.health_check()
        RAG_HEALTHY = is_healthy
        if is_healthy:
            log.info(f"RAG health check passed - routing enabled")
        else:
            log.warning(f"RAG health check failed - routing disabled")
        return {"rag_healthy": is_healthy, "service_url": RAG_SERVICE_URL, "routing_enabled": RAG_HEALTHY}
    except Exception as e:
        RAG_HEALTHY = False
        log.warning(f"RAG health check failed: {e} - routing disabled")
        return {"rag_healthy": False, "reason": str(e), "routing_enabled": False}


@app.post("/webhook/jotform")
async def jotform_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_webhook_api_key)
):
    """Receives Jotform form submissions."""
    try:
        raw = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Idempotency key — prefer Jotform's submission ID, fall back to payload hash
    submission_id = raw.get("submissionID") or raw.get("submission_id") or raw.get("formID")
    idempotency_key = submission_id or hashlib.sha256(
        json.dumps(raw, sort_keys=True).encode()
    ).hexdigest()

    if is_duplicate(idempotency_key):
        log.info(f"Duplicate Jotform submission skipped: {idempotency_key}")
        return JSONResponse({"status": "skipped", "reason": "duplicate"}, status_code=200)

    lead: dict = {}
    for k, val in raw.items():
        k_lower = k.lower()
        if any(x in k_lower for x in ["name", "fullname", "full_name"]):
            lead["name"] = str(val).strip()
        elif any(x in k_lower for x in ["email", "mail"]):
            lead["email"] = str(val).strip().lower()
        elif any(x in k_lower for x in ["phone", "mobile", "tel"]):
            lead["phone"] = str(val).strip()
        elif any(x in k_lower for x in ["company", "organization", "business"]):
            lead["company"] = str(val).strip()
        elif any(x in k_lower for x in ["service", "request", "type"]):
            lead["service"] = str(val).strip()

    lead["source"]  = "jotform_form"
    lead["form_id"] = raw.get("formID", raw.get("form_id", "unknown"))

    if not lead.get("email") and not lead.get("phone"):
        return JSONResponse({"status": "skipped", "reason": "no contact info"}, status_code=200)

    # DB write first — always before any side effects
    lead_id = store_lead(lead)
    store_form_submission({**lead, **raw}, lead_id, idempotency_key)
    log_event(lead_id, "form_submitted", {"source": "jotform", "form_id": lead["form_id"]})

    # Respond immediately — emails run in background
    background_tasks.add_task(dispatch_emails, lead, lead_id, "Jotform Form Submission")

    return JSONResponse({"status": "success", "lead_id": lead_id})


@app.post("/webhook/agent")
async def agent_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    authenticated: bool = Depends(verify_webhook_api_key)
):
    """Receives Robin AI agent lead capture data with RAG routing."""
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON payload")

    # Extract agent data
    lead = {
        "name":       data.get("name") or data.get("visitor_name"),
        "company":    data.get("company") or data.get("visitor_company"),
        "email":      data.get("email") or data.get("visitor_email"),
        "phone":      data.get("phone") or data.get("visitor_phone"),
        "service":    data.get("service") or data.get("services_enquired"),
        "source":     "robin_ai_agent",
        "session_id": data.get("session_id"),
        "summary":    data.get("conversation_summary", ""),
        "intent":     data.get("intent", "unknown"),
        "message":    data.get("last_message", ""),
    }

    if not lead.get("email") and not lead.get("phone"):
        return JSONResponse({"status": "skipped", "reason": "no contact info"}, status_code=200)

    # Store lead first (RAG failure does not block lead capture)
    lead_id = store_lead(lead)

    # Hard RAG routing for specific intents (after lead_id is assigned)
    rag_response = None
    if should_route_to_rag(lead.get("intent", ""), lead.get("message", "")):
        log.info(f"[RAG] Routing intent={lead.get('intent')} to RAG service")
        rag_result = await query_rag_safely(
            lead.get("message", ""),
            lead.get("intent", ""),
            caller="robin_ai_agent"
        )

        if rag_result["success"]:
            rag_response = compose_sales_response_with_rag(rag_result, lead.get("intent", ""))
            log_event(lead_id, "rag_query_success", {
                "intent": lead.get("intent"),
                "query": lead.get("message", "")[:100],
                "latency": rag_result["latency"],
                "sources_count": len(rag_result.get("sources", [])),
            })
        else:
            log.warning(f"[RAG] Query failed: {rag_result.get('error')}")
            log_event(lead_id, "rag_query_failed", {
                "intent": lead.get("intent"),
                "query": lead.get("message", "")[:100],
                "error": rag_result.get("error"),
                "latency": rag_result["latency"],
            })

    if lead.get("session_id"):
        conn = get_db()
        cur  = conn.cursor()
        try:
            cur.execute(
                """INSERT INTO agent_conversations
                       (session_id, visitor_name, visitor_company, visitor_email,
                        visitor_phone, services_enquired, conversation_summary,
                        lead_captured, lead_id, jotform_agent_id, started_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, true, %s,
                           '019dbd271be77876b7e36ce06ac88fd491ef', NOW())
                   ON CONFLICT (session_id) DO UPDATE SET
                       lead_captured        = true,
                       lead_id              = EXCLUDED.lead_id,
                       conversation_summary = EXCLUDED.conversation_summary""",
                (
                    lead["session_id"],
                    lead["name"],
                    lead["company"],
                    lead["email"],
                    lead["phone"],
                    [lead["service"]] if lead.get("service") else [],
                    lead.get("summary", ""),
                    lead_id,
                ),
            )
            conn.commit()
        except Exception as e:
            log.error(f"agent_conversations insert failed: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()

    log_event(lead_id, "agent_interaction", {
        "session_id": lead.get("session_id"),
        "intent": lead.get("intent"),
        "rag_used": rag_response is not None,
        "services":   lead.get("service"),
        "summary":    lead.get("summary", "")[:200]
    })

    background_tasks.add_task(dispatch_emails, lead, lead_id, "Robin AI Agent")

    return JSONResponse({
        "status": "success",
        "lead_id": lead_id,
        "rag_response": rag_response if rag_response else None
    })


@app.get("/leads")
async def get_leads(
    status: Optional[str] = None,
    limit: int = 50,
    fields: Optional[str] = None,
    authenticated: bool = Depends(verify_api_key)
):
    """
    Quick lead dashboard endpoint with field filtering and auth.

    Query params:
    - status: Filter by lead status
    - limit: Max results (default 50, max 100)
    - fields: Comma-separated field names to return (e.g., "id,name,email")
    """
    # Enforce pagination cap
    limit = min(limit, 100)

    # Parse field filter
    field_list = None
    if fields:
        field_list = [f.strip() for f in fields.split(",")]

    conn = get_db()
    cur  = conn.cursor()
    try:
        if status:
            cur.execute(
                "SELECT * FROM leads WHERE status = %s ORDER BY created_at DESC LIMIT %s",
                (status, limit)
            )
        else:
            cur.execute(
                "SELECT * FROM leads ORDER BY created_at DESC LIMIT %s", (limit,)
            )
        leads = cur.fetchall()

        # Apply field filtering
        if field_list:
            filtered_leads = []
            for lead in leads:
                lead_dict = dict(lead)
                # Convert datetime objects to ISO strings
                for k, v in lead_dict.items():
                    if isinstance(v, datetime):
                        lead_dict[k] = v.isoformat()
                filtered = {k: v for k, v in lead_dict.items() if k in field_list}
                filtered_leads.append(filtered)
            return JSONResponse({"leads": filtered_leads, "count": len(filtered_leads)})

        # Convert datetime objects to ISO strings
        leads_serializable = []
        for lead in leads:
            lead_dict = dict(lead)
            for k, v in lead_dict.items():
                if isinstance(v, datetime):
                    lead_dict[k] = v.isoformat()
            leads_serializable.append(lead_dict)
        return JSONResponse({"leads": leads_serializable, "count": len(leads_serializable)})
    finally:
        cur.close()
        conn.close()


@app.get("/leads/{lead_id}/events")
async def get_lead_events(
    lead_id: int,
    authenticated: bool = Depends(verify_api_key)
):
    """Return full event timeline for a lead."""
    conn = get_db()
    cur  = conn.cursor()
    try:
        cur.execute(
            "SELECT * FROM lead_events WHERE lead_id = %s ORDER BY created_at ASC",
            (lead_id,)
        )
        events = cur.fetchall()
        # Convert datetime objects to ISO strings
        events_serializable = []
        for event in events:
            event_dict = dict(event)
            for k, v in event_dict.items():
                if isinstance(v, datetime):
                    event_dict[k] = v.isoformat()
            events_serializable.append(event_dict)
        return JSONResponse({"lead_id": lead_id, "events": events_serializable})
    finally:
        cur.close()
        conn.close()


@app.get("/leads/hot")
async def get_hot_leads(limit: int = 20):
    """Get HOT and WARM leads with scores and RAG intent."""
    conn = get_db()
    cur = conn.cursor()
    try:
        cur.execute(
            """
            SELECT id, full_name, company_name, email, phone,
                   services_required, lead_score, score_band,
                   rag_intent, rag_confidence, recommended_action,
                   scored_at, created_at
            FROM leads
            WHERE score_band IN ('HOT', 'WARM')
            ORDER BY lead_score DESC, scored_at DESC NULLS LAST
            LIMIT %s
            """,
            (limit,)
        )
        leads = cur.fetchall()

        # Serialize
        results = []
        for lead in leads:
            lead_dict = dict(lead)
            for k, v in lead_dict.items():
                if isinstance(v, datetime):
                    lead_dict[k] = v.isoformat() if v else None
            results.append(lead_dict)

        return JSONResponse({
            "count": len(results),
            "leads": results
        })
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("webhook_server_v4_rag:app", host="0.0.0.0", port=8080, reload=False)
