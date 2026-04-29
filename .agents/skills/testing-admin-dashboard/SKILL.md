# Testing: RAG Admin Dashboard & AI Test Lab

## Overview
The admin dashboard at `/admin` is a single-page HTML app (`static/admin.html`) with 5 tabs: Overview, Query History, Monitoring, AI Test Lab, Dispatch Test. All endpoints are protected by `ADMIN_TOKEN` via `X-Admin-Token` header or `?token=` query param.

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
```

## Testing the AI Test Lab

### Browser Flow
1. Open `http://localhost:8000/admin?token=<ADMIN_TOKEN>`
2. Click "AI Test Lab" tab (4th tab)
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

### Auth Enforcement (curl)
```bash
# Should return 401
curl -s -X POST http://localhost:8000/api/dashboard/eval-cases \
  -H "Content-Type: application/json" \
  -d '{"query":"x","feedback_label":"bad"}'

# Should return {"status":"ok","saved":true}
curl -s -X POST http://localhost:8000/api/dashboard/eval-cases \
  -H "Content-Type: application/json" \
  -H "X-Admin-Token: test-secret-token-123" \
  -d '{"query":"x","feedback_label":"bad","must_include":"AED"}'

# Token via query param also works
curl -s -X POST "http://localhost:8000/api/dashboard/eval-cases?token=test-secret-token-123" \
  -H "Content-Type: application/json" \
  -d '{"query":"x","feedback_label":"bad"}'
```

### Validation (422 errors)
- Missing `query` → 422
- Missing `feedback_label` → 422

## Common Pitfalls
- **No Ollama:** Dispatch returns 503 — this is expected in degraded mode. UI/auth/persistence still testable.
- **httpx not installed:** `TestClient` from Starlette requires `httpx`. Use curl or browser testing instead if httpx is unavailable.
- **Double-click save:** The Save button disables for 1 second after save to prevent rapid duplicates.
- **Meta cards missing:** In degraded mode (503 response), meta cards (intent, failure_type, latency, sources) may not render since there's no full payload. This is normal.
- **JSONL file location:** `data/eval_cases.jsonl` — the `data/` directory is auto-created on first save.

## Regression Checks
- After changes to `admin.html`, verify all 5 tabs still render (Overview, Query History, Monitoring, AI Test Lab, Dispatch Test)
- Overview should show KPI cards (System Status, RAG Ready, Indexes, Total Leads, etc.)
- Switching tabs should hide/show correct content
