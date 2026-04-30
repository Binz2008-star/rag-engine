# RAG Intent System

## Bootstrap

1. Put your documents in `data/docs/`
2. Put your intent datasets in:
   - `data/intent_dataset_base.jsonl`
   - `data/intent_dataset_human.jsonl`
3. Train the initial router:

```bash
python scripts/run_training.py
```

4. Build retrieval indexes:

```bash
python scripts/build_indexes.py
```

5. Run the API:

```bash
uvicorn api.server.main:app --reload
```

6. Check system health:

```bash
curl http://127.0.0.1:8000/health
```

## Runtime Status

### Health Endpoints

**`GET /health`** - System health check (legacy)
```json
{
  "status": "ok",
  "pipeline_ready": true,
  "version": "1.0.0",
  "chat_model": "qwen-agent",
  "index_count": 3
}
```

**`GET /api/health`** - Lightweight health probe
```json
{
  "status": "ok",
  "rag_ready": true,
  "index_count": 3,
  "timestamp": 1714540800.0
}
```

### Status Interpretation

- `pipeline_ready` / `rag_ready`: RAG service has initialized and indexes are loaded
- `index_count`: Number of available retrieval indexes (eco, cv, general)
- `chat_model`: Active LLM model from configuration

## Admin Dashboard

Access the admin dashboard at `http://127.0.0.1:8000/admin`

### Authentication

Set `ADMIN_TOKEN` environment variable before starting the server. If not set, a random token is generated and logged at startup.

### Features

- **Overview**: System KPIs, recent leads, monitoring summary
- **Query History**: Filterable lead list with flag/rerun actions
- **Monitoring**: Latency metrics, failure rates, channel breakdown
- **AI Test Lab**: Interactive query testing with feedback capture
- **RAG Config**: Runtime parameter adjustment (top_k, score_threshold, etc.)
- **Dispatch Test**: Direct `/api/dispatch` endpoint testing

### Integration Boundaries

**Wired (Live)**
- Admin dashboard UI → API endpoints
- Lead capture and storage
- Query dispatch through RAG pipeline
- Eval case persistence (JSONL)
- RAG config file I/O (`data/rag_runtime_config.json`)

**Not Wired (UI Only)**
- RAG config changes are saved to disk but **not** applied to the running pipeline
- To apply config changes: restart the server or implement config hot-reload
- Operator Console (`/admin/operator`) exists but requires `static/operator.html`

## Notes

* This is single-node by design.
* Events are stored in SQLite at `logs/events.db`.
* Retraining is batch-triggered, not inline with inference.
* `uncertain` routing blends all indexes instead of silently collapsing to `general`.
* Training promotion should use real eval metrics, not placeholders.
* Admin dashboard requires token authentication via `X-Admin-Token` header.
