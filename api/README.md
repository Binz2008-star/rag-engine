# RAG Assistant API

FastAPI wrapper around the **eval-certified** pipeline
(`app.pipeline.Pipeline` + `app.inference_service.InferenceService`). No
pipeline logic is reimplemented — the gateway only exposes HTTP, applies
CORS, and shapes responses. This guarantees that a PASS on the strict
evaluation gate predicts the behaviour users see via HTTP.

## Endpoints

| Method | Path          | Description                                     |
| ------ | ------------- | ----------------------------------------------- |
| GET    | `/api/health` | Liveness + pipeline readiness + index count     |
| POST   | `/api/query`  | Run a question through the evaluated pipeline   |

Streaming is intentionally not exposed. `Pipeline.run()` returns a fully
formed result; a synthetic token stream would bypass the pipeline's
grounding gate and re-duplicate policy checks, reintroducing the exact
runtime/eval drift this service is designed to eliminate.

### Response schema (`POST /api/query`)

```json
{
  "answer": "string",
  "sources": [
    { "source": "file.pdf", "chunk_id": "c_12", "doc_type": "pdf", "score": 0.82 }
  ],
  "latency_ms": 2244,
  "wall_ms": 2280,
  "request_id": "api_1713694112084",
  "intent": "eco",
  "intent_confidence": 1.0,
  "intent_method": "rules",
  "intent_method_raw": "rule",
  "grounded": true,
  "failure_type": null,
  "model_version": "v1.0.0",
  "retriever_version": "v1_a3f2c19d"
}
```

`latency_ms` is what the pipeline measures internally (the value the eval
gate sees). `wall_ms` is the API wall-clock including the thread hop and
JSON serialisation. No split retrieval/generation timings are reported
because the canonical pipeline does not record them — inventing split
values would fabricate data.

## Run

From the project root (`d:\AI\assistant`), using the same venv you use
for the RAG app and CI:

```powershell
# 1. Install the API-only extras into the existing venv
pip install -r api\requirements.txt

# 2. (Optional) override API-side env
Copy-Item api\.env.example api\.env

# 3. Make sure the indexes exist (same artefacts used by eval_runner.py)
python scripts\build_indexes.py

# 4. Launch
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir api
```

Swagger UI: <http://localhost:8000/docs>

## Smoke test

```powershell
# Health
curl http://localhost:8000/api/health

# Query (defaults to the qwen2:1.5b chat model configured in the project root .env)
curl -X POST http://localhost:8000/api/query `
  -H "Content-Type: application/json" `
  -d '{"question":"What does ECO do?"}'
```

## Acceptance test: eval/product parity

The only meaningful proof that CI and the product are aligned is a cold
run where a query passed by `eval_runner.py` returns byte-identical
`answer` + `sources` through `/api/query`:

```powershell
# 1. Run the strict eval offline
python eval_runner.py --mode strict --report reports\ci_eval_strict.json

# 2. Pick a PROMOTE-eligible query (e.g. "What is Eco company?") and
#    POST it against a fresh API boot. Diff the answer + sources against
#    the entry in reports\ci_eval_strict.json.
```

If the two disagree, treat it as a P0: the API has drifted from the
evaluated pipeline.

## Notes

- The API package is `server` (not `app`) to avoid a name clash with the
  parent project's `app` package, which the gateway imports from directly.
- Ollama / chat-model configuration is owned by `app.config` and consumed
  by `generation.llm.LLMClient`. Do not redefine it in `api/.env`.
- Pipeline initialisation is async-safe: blocking calls run via
  `asyncio.to_thread` so FastAPI's event loop stays responsive under
  concurrent requests.
