# Testing: RAG Admin Dashboard & AI Test Lab

## Overview
The admin dashboard at `/admin` is a single-page HTML app (`static/admin.html`) with 6 tabs: Overview, Query History, Monitoring, AI Test Lab, RAG Config, Dispatch Test. All endpoints are protected by `ADMIN_TOKEN` via `X-Admin-Token` header or `?token=` query param.

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
python -m py_compile api/server/services/rag_config.py
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

# Validate latest line is valid JSON with config_version
tail -1 data/eval_cases.jsonl | python3 -c "import sys,json; obj=json.loads(sys.stdin.read()); print('OK:', obj['query'], obj['feedback_label'], obj['must_include'], 'config_version='+str(obj.get('config_version')))"
```

**Key normalization:** `must_include` accepts comma-separated string input (e.g. "AED, grease trap") and stores it as array (`["AED", "grease trap"]`).

## Testing RAG Config Tab (config_version Traceability)

The RAG Config tab allows viewing/editing runtime config parameters. Config is stored in `data/rag_runtime_config.json`. The `config_version` field is automatically included in eval case saves and dispatch responses.

### Browser Flow
1. Click "RAG Config" tab
2. Verify defaults load: top_k=15, score_threshold=0.38, max_context_chars=3000, temperature=0.2, reranker_enabled=Enabled, grounding_strictness=0.5
3. Verify Config Metadata shows: Version v1, Updated At "Never", Updated By "—"
4. Change top_k to 20 → click "Save Config"
5. Verify: "Saved! (v2)" appears, Version card shows v2, Updated At shows timestamp, Updated By shows "admin"

### config_version Progression Test
This is the key Phase 10 traceability test:
1. **Clean data first:** `rm -f data/eval_cases.jsonl data/rag_runtime_config.json`
2. Save eval case in AI Test Lab (default config) → verify JSONL has `config_version: 1`
3. Go to RAG Config → change a value → Save (bumps to v2)
4. Save another eval case in AI Test Lab → verify JSONL has `config_version: 2`
5. Shell verification:
```bash
cat data/eval_cases.jsonl | python3 -c "
import sys, json
lines = [l for l in sys.stdin.read().strip().split('\n') if l.strip()]
for i, line in enumerate(lines):
    d = json.loads(line)
    print(f'Line {i+1}: config_version={d.get(\"config_version\")}')
"
```

### Config File Verification
```bash
# After saving config from RAG Config tab
cat data/rag_runtime_config.json | python3 -m json.tool
# Should show version, updated_at, updated_by, and config values
```

## Auth Enforcement (curl)
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
- **Config file location:** `data/rag_runtime_config.json` — auto-created on first config save from dashboard.
- **config_version in 503 mode:** In degraded mode, dispatch returns 503 error JSON without `config_version`. The `config_version` field only appears in successful dispatch responses. Eval case saves always include `config_version` regardless of dispatch mode.
- **Clean data for testing:** Remove both `data/eval_cases.jsonl` and `data/rag_runtime_config.json` before testing config_version progression to start from known defaults (v1).

## Regression Checks
- After changes to `admin.html`, verify all 6 tabs still render (Overview, Query History, Monitoring, AI Test Lab, RAG Config, Dispatch Test)
- Overview should show KPI cards (System Status, RAG Ready, Indexes, Total Leads, etc.)
- Switching tabs should hide/show correct content
- RAG Config defaults should load even without `data/rag_runtime_config.json`
