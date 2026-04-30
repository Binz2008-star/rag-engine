# Testing: RAG Admin Dashboard & AI Test Lab

## Overview
The admin dashboard at `/admin` is a single-page HTML app (`static/admin.html`) with 6 tabs: Overview, Query History, Monitoring, AI Test Lab, RAG Config, Dispatch Test. All endpoints are protected by `ADMIN_TOKEN` via `X-Admin-Token` header or `?token=` query param (GET only).

## Devin Secrets Needed
- `ADMIN_TOKEN` — admin dashboard auth token (use `test-secret-token-123` for local dev)

## Server Setup
```bash
export ADMIN_TOKEN="test-secret-token-123"
export OLLAMA_BASE_URL="http://localhost:11434"
python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir api
```

**Degraded mode:** If Ollama is not running, the server starts in degraded mode (RAG Ready = false). The dashboard still works for UI/auth testing — dispatch queries return 503 "RAG pipeline not ready".

## Compile Gate (always run first)
```bash
python -m py_compile api/server/main.py
python -m py_compile api/server/admin_routes.py
```

## Testing the AI Test Lab

### Browser Flow
1. Open `http://localhost:8000/admin?token=<ADMIN_TOKEN>`
2. Click "AI Test Lab" tab
3. Type a query (e.g. "What are your grease trap prices?") and click Send
4. Verify: ANSWER section appears with response text
5. Click a feedback button (Good/Bad/Wrong Source/Too Slow/False Refusal)
6. Verify: button highlights, Feedback Label field auto-fills, Save Eval Case button enables (green)
7. Fill eval form: Expected Intent, Expected Source, Must Include (comma-separated), Notes
8. Click "Save Eval Case"
9. Verify: "Saved!" text appears, Saved Eval Cases table updates with new row

### JSONL Persistence Verification
```bash
# File should exist after first save
cat data/eval_cases.jsonl

# Validate latest line is valid JSON
tail -1 data/eval_cases.jsonl | python -c "import sys,json; obj=json.loads(sys.stdin.read()); print('OK:', obj['query'], obj['feedback_label'], obj['must_include'])"
```

**Key normalization:** `must_include` accepts comma-separated string input (e.g. "AED, grease trap") and stores it as array (`["AED", "grease trap"]`).

### Feedback Label Validation
Valid labels: `good`, `bad`, `wrong_source`, `too_slow`, `false_refusal`. Any other value returns 422.
```bash
curl -s -X POST http://localhost:8000/api/dashboard/eval-cases \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: test-secret-token-123" \
  -d '{"query":"x","feedback_label":"invalid"}'
# Expected: 422 with list of valid labels
```

## Testing RAG Config Tab

### Browser Flow
1. Click "RAG Config" tab
2. Verify defaults load: top_k=15, score_threshold=0.38, max_context_chars=3000, temperature=0.2, reranker_enabled=Enabled, grounding_strictness=0.5
3. Verify Config Metadata shows: VERSION v1, UPDATED AT "Never"
4. Change top_k to 20, click "Save Config"
5. Verify: "Saved! (v2)" green text, Version shows v2, Updated At has timestamp, Updated By shows "admin"

### Config File Verification
```bash
cat data/rag_runtime_config.json | python -m json.tool
# Should show top_k=20, version=2, updated_by="admin"
```

### Config API
```bash
# GET config
curl -s http://localhost:8000/api/dashboard/rag-config \
  -H "X-Admin-Token: test-secret-token-123" | python -m json.tool

# POST config update
curl -s -X POST http://localhost:8000/api/dashboard/rag-config \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: test-secret-token-123" \
  -d '{"top_k":25,"notes":"testing"}'
```

## Auth Enforcement

**Important:** POST endpoints require `X-Admin-Token` header. The `?token=` query param is accepted for `/admin` GET (browser access) but **NOT** for POST write endpoints.

```bash
# Should return 401 — no token
curl -s -o /dev/null -w "%{http_code}" -X POST http://localhost:8000/api/dashboard/eval-cases \
  -H "Content-Type: application/json" \
  -d '{"query":"x","feedback_label":"bad"}'

# Should return 401 — ?token= only (no header)
curl -s -o /dev/null -w "%{http_code}" -X POST "http://localhost:8000/api/dashboard/eval-cases?token=test-secret-token-123" \
  -H "Content-Type: application/json" \
  -d '{"query":"x","feedback_label":"bad"}'

# Should return 200 — X-Admin-Token header
curl -s -X POST http://localhost:8000/api/dashboard/eval-cases \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: test-secret-token-123" \
  -d '{"query":"x","feedback_label":"bad","must_include":"AED"}'
```

## Diff Scope Verification

When working on dashboard-only PRs, always verify no RAG/retrieval/router files leaked into the diff:
```bash
git diff --name-only main...HEAD
```

**Allowed files** (dashboard/eval-case scope):
- `api/server/admin_routes.py`
- `api/server/main.py`
- `api/server/services/leads_store.py`
- `api/server/whatsapp_routes.py`
- `requirements.txt`
- `static/admin.html`

**Disallowed files** (RAG/retrieval scope):
- `retrieval/*`
- `router/*`
- `generation/*`
- `app/pipeline.py`
- `api/server/services/rag_service.py`

## Common Pitfalls
- **No Ollama:** Dispatch returns 503 — this is expected in degraded mode. UI/auth/persistence still testable.
- **httpx not installed:** `TestClient` from Starlette requires `httpx`. Use curl or browser testing instead if httpx is unavailable.
- **Double-click save:** The Save button disables for 1 second after save to prevent rapid duplicates.
- **Meta cards missing:** In degraded mode (503 response), meta cards (intent, failure_type, latency, sources) may not render since there's no full payload. This is normal.
- **JSONL file location:** `data/eval_cases.jsonl` — the `data/` directory is auto-created on first save.
- **Config file location:** `data/rag_runtime_config.json` — auto-created with defaults on first GET.
- **Server restart needed:** If you edit backend Python files, you may need to restart the uvicorn server (or use `--reload`) for changes to take effect. Old code running on a stale server is a common source of test failures.
- **?token for POST:** Do NOT use `?token=` for POST endpoints — only `X-Admin-Token` header is accepted for writes.

## Regression Checks
- After changes to `admin.html`, verify all 6 tabs still render (Overview, Query History, Monitoring, AI Test Lab, RAG Config, Dispatch Test)
- Overview should show KPI cards (System Status, RAG Ready, Indexes, Total Leads, etc.)
- Switching tabs should hide/show correct content
- Eval case save should still work after RAG Config changes and vice versa
