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
uvicorn app.main:app --reload
```

6. Check system health:

```bash
curl http://127.0.0.1:8000/health
```

## Notes

* This is single-node by design.
* Events are stored in SQLite at `logs/events.db`.
* Retraining is batch-triggered, not inline with inference.
* `uncertain` routing blends all indexes instead of silently collapsing to `general`.
* Training promotion should use real eval metrics, not placeholders.

---

## Chat UI + API gateway

Production-grade chat frontend (Next.js) + API gateway (FastAPI) wrapping
the existing `app.rag_pipeline.RagPipeline`. No pipeline logic is duplicated.

```
Next.js (frontend/)  ->  FastAPI (api/)  ->  RagPipeline (app/)  ->  Ollama
```

See [`api/README.md`](api/README.md) and [`frontend/README.md`](frontend/README.md)
for full details. Quick start:

### Backend

```powershell
# From the project root, using your existing Python venv
pip install -r api\requirements.txt
Copy-Item api\.env.example api\.env   # optional overrides
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir api
```

- Health: <http://localhost:8000/api/health>
- Docs:   <http://localhost:8000/docs>

### Frontend

```powershell
cd frontend
npm install
Copy-Item .env.example .env.local     # optional overrides
npm run dev
```

Open <http://localhost:3000>.

### Smoke tests

```powershell
# Health
curl http://localhost:8000/api/health

# Non-streaming query
curl -X POST http://localhost:8000/api/query `
  -H "Content-Type: application/json" `
  -d '{"question":"What does ECO do?"}'

# SSE stream
curl -N -X POST http://localhost:8000/api/stream `
  -H "Content-Type: application/json" `
  -d '{"question":"Summarize Robin Edwan CV."}'
```
