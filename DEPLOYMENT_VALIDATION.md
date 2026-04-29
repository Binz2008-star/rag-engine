# Render Runtime Validation

## Current Render Configuration

### Service Definition (render.yaml)
- **Service name**: eco-pipeline-webhook
- **Start command**: `uvicorn pipeline.webhook_server:app --host 0.0.0.0 --port $PORT`
- **Entry point**: `pipeline/webhook_server.py`
- **Environment**: production

### Environment Variables in render.yaml
```yaml
PYTHON_VERSION: "3.11"
DATABASE_URL: (sync from Render)
API_KEY: (sync from Render)
GMAIL_USER: (sync from Render)
GMAIL_APP_PASSWORD: (sync from Render)
JOTFORM_API_KEY: (sync from Render)
OLLAMA_BASE_URL: http://localhost:11434/api
ENV: production
COMPANY_NAME: ECO Technology Environmental Protection Services LLC
COMPANY_PHONE: +971 52 223 3989
WEBSITE: https://binz2008-star.github.io/eco-environmental-uae
```

### Missing Environment Variables
**CRITICAL**: The following variables are NOT set in render.yaml but are required:

1. **RAG_SERVICE_URL** - Defaults to `http://localhost:8001` (will fail in production)
2. **RAG_ENABLED** - Defaults to `true` but without RAG_SERVICE_URL, RAG will be degraded
3. **ADMIN_USERNAME** - Required for /admin endpoints
4. **ADMIN_PASSWORD** - Required for /admin endpoints
5. **NOTIFY_EMAIL** - Used in webhook_server but not in render.yaml

## Endpoint Status

### /health Endpoint
**Status**: ✅ Available
- Location: `pipeline/webhook_server.py` line 713
- Returns: `{"status": "ok", "version": "4.1", "phase": "2", "rag": {...}, "scoring_available": bool}`
- RAG status included in response

### /admin Endpoints
**Status**: ⚠️ Available but requires configuration
- `/admin` - HTML dashboard (pipeline/webhook_server.py line 1134)
- `/admin/stats` - Aggregate KPIs (pipeline/webhook_server.py line 1328)
- `/admin/leads/{lead_id}` - Lead detail (pipeline/webhook_server.py line 1355)
- **Requirement**: ADMIN_USERNAME and ADMIN_PASSWORD must be set in Render env vars
- **Auth**: HTTP Basic Authentication

### Webhook Endpoints
**Status**: ✅ Available
- `POST /webhook/jotform` - Jotform form submissions
- `POST /webhook/agent` - Robin AI agent lead captures
- **Requirement**: API_KEY must be set (unless ENV=development)

### RAG Health Endpoint
**Status**: ✅ Available
- `GET /rag/health` - RAG service health check
- Returns: `{"rag_healthy": bool, "service_url": str, "routing_enabled": bool}`

## RAG Configuration Analysis

### Current Behavior
```python
RAG_SERVICE_URL = os.environ.get("RAG_SERVICE_URL", "http://localhost:8001")
RAG_ENABLED = os.environ.get("RAG_ENABLED", "true").lower() == "true"
```

### Production State
**Without RAG_SERVICE_URL set in Render:**
- RAG_SERVICE_URL will default to `http://localhost:8001`
- This will FAIL in production (localhost doesn't exist)
- RAG health check will fail
- RAG routing will be disabled (graceful degradation)
- Lead capture will continue without RAG enrichment

### Required Actions for RAG in Production
1. **Set RAG_SERVICE_URL** in Render environment variables to actual RAG service URL
2. **Set RAG_ENABLED** to `true` if RAG service is available
3. **OR set RAG_ENABLED** to `false` to run in degraded mode intentionally

## Recommendations

### Immediate Actions Required
1. Add missing environment variables to render.yaml:
   ```yaml
   envVars:
     - key: RAG_SERVICE_URL
       value: "https://your-rag-service-url.com"  # Update with actual URL
     - key: RAG_ENABLED
       value: "true"  # or "false" for degraded mode
     - key: ADMIN_USERNAME
       sync: false
     - key: ADMIN_PASSWORD
       sync: false
     - key: NOTIFY_EMAIL
       value: "robenedwan@gmail.com"
   ```

2. Decide on RAG strategy:
   - **Option A**: Deploy RAG service separately and set RAG_SERVICE_URL
   - **Option B**: Run in degraded mode (set RAG_ENABLED=false)
   - **Option C**: Keep current (RAG will auto-disable due to localhost URL)

### Verification Steps
1. Test `/health` endpoint after deployment
2. Test `/admin` endpoint with configured credentials
3. Test webhook endpoint with API_KEY
4. Check `/rag/health` to confirm RAG status
5. Verify lead capture works without RAG (degraded mode)

## Production Mode Decision

**Current state**: RAG will be **degraded** (disabled) because:
- RAG_SERVICE_URL defaults to localhost:8001
- No RAG service is deployed on Render
- Health check will fail
- Routing will be disabled
- Lead capture continues without RAG enrichment

**This is acceptable** per the decision to "freeze RAG eval fixes" and focus on deployment validation.
