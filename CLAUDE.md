# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Architecture Overview

This is a **RAG Intent System** — a retrieval-augmented generation assistant built around a personal corpus (Robin Edwan CV + ECO Technology company documents). The system routes queries by intent, retrieves grounded context, and generates English-only answers via a local Ollama LLM.

### Request flow (production path)

```
Next.js (frontend/)  →  FastAPI gateway (api/server/)  →  app.pipeline.Pipeline  →  Ollama (qwen2:1.5b)
```

### Request flow (legacy/standalone path)

```
app/main.py (FastAPI)  →  app.rag_pipeline.RagPipeline  →  Ollama
```

`app/pipeline.py` (`Pipeline`) is the **eval-certified** path consumed by the API gateway and `eval_runner.py`. `app/rag_pipeline.py` (`RagPipeline`) is **deprecated** — it pre-dates the grounding gate unification. Do not add features to it or use it as a reference for new code.

### Intent routing

`router/intent_router.py` (`IntentRouter`) routes each query to one of three index namespaces: `cv`, `eco`, or `general`. Routing uses rule-based hints first (`router/features.py`), falling back to a trained sklearn classifier (`models/intent_bootstrap.joblib`). An `uncertain` route blends all indexes instead of silently collapsing to `general`.

### Retrieval

`retrieval/faiss_index.py` wraps per-namespace FAISS indexes stored under `models/` (`cv.faiss`, `eco.faiss`, `general.faiss`). `retrieval/multi_retriever.py` dispatches to the right index and merges results. `retrieval/reranker.py` re-scores hits by cosine similarity before the grounding gate.

### Grounding gate (v1.0 invariant — do not break)

`generation/grounding.py::check_grounding()` is the **sole authoritative grounding gate** for both the runtime pipeline and the evaluator. When it rejects an answer (cosine < 0.60), the pipeline replaces the answer with `"Insufficient data."` and classifies the failure as `retrieval_miss`. The weaker token-overlap check (`_is_grounded`) was removed at v1.0. Any change that makes `check_grounding` no longer the sole gate will fail `test_grounding_gate_authority.py`.

### Evaluation gate

`evaluation/eval_gate.py::gate()` is the promotion gate. Required for PROMOTE:
- `pass_rate >= 0.95`
- `hallucination_rate == 0.0`
- `refusal_accuracy == 1.0`
- `domain_accuracy >= 0.95`
- `ocr_presence_check is True` (strict boolean, not truthy)
- All queries with `killer: true` must pass

### Event sourcing

`events/` stores query events in SQLite (`logs/events.db`). `analysis/drift_detector.py` watches for model drift; `analysis/alerts.py` surfaces anomalies. `workers/` contains the background consumer and retraining trigger.

### API gateway (`api/`)

The package inside `api/` is named `server` (not `app`) to avoid a name clash with the parent `app` package. The gateway imports `app.pipeline.Pipeline` directly — no pipeline logic is duplicated.

**No streaming endpoint.** It was intentionally removed. A faked SSE layer would bypass the grounding gate and duplicate policy checks, reintroducing the eval/product drift the gateway exists to eliminate. Do not re-add `/api/stream`.

**Ollama fail-fast.** If Ollama is unreachable at startup, `lifespan` raises `SystemExit(1)`. This is intentional — not a bug to suppress or work around.

**Frozen response schema** (`api/server/schemas.py::QueryResponse`). Do not add, remove, or rename fields without a gate re-run:

| Field | Type | Notes |
|---|---|---|
| `answer` | `str` | |
| `sources` | `list[Source]` | `source`, `chunk_id`, `doc_type`, `score` |
| `latency_ms` | `int` | pipeline-measured; single value — no split retrieval/generation |
| `wall_ms` | `int` | API wall-clock including thread hop + serialisation |
| `request_id` | `str` | |
| `intent` | `str` | `cv` \| `eco` \| `general` \| `uncertain` |
| `intent_confidence` | `float` | |
| `intent_method` | `str` | coarse: `rules` \| `v2_model` |
| `intent_method_raw` | `str` | raw router label (observability only) |
| `grounded` | `bool` | |
| `failure_type` | `str \| null` | `"retrieval_miss"` or `null` — these are the only two values the production pipeline emits |
| `model_version` | `str` | |
| `retriever_version` | `str` | |

## Key configuration

`app/config.py` is the single source of truth for:
- `CHAT_MODEL` — Ollama chat model (default `llama3`; CI pins `qwen2:1.5b`)
- `EMBED_MODEL` — embedding model (`nomic-embed-text`)
- `REFUSAL_MESSAGE` — canonical refusal string (`"Insufficient data."`) — import this constant, never hard-code the literal
- `PRODUCTION_MODE` — when `False` (eval mode), enables deterministic keyword grounding and contract enforcement
- `TOP_K`, `CHUNK_SIZE`, `CHUNK_OVERLAP`, `ROUTER_CONFIDENCE_THRESHOLD` — **frozen at v1.0; do not change without a reproducible failure case**

Environment overrides via `.env` at the project root.

## Commands

### Bootstrap (first run)

```powershell
python scripts/run_training.py          # train intent classifier
python scripts/build_indexes.py         # build FAISS indexes
```

### Run the legacy app (standalone)

```powershell
uvicorn app.main:app --reload
```

### Run the API gateway

```powershell
pip install -r api\requirements.txt
uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir api
```

### Run the frontend

```powershell
cd frontend
npm install
npm run dev
```

### Run the full evaluation suite

```powershell
python eval_runner.py                              # uses tests/eval_queries.json
python eval_runner.py --report reports/run_01.json
python eval_runner.py --mode strict                # strict mode (authoritative)
python eval_runner.py --fast                       # skip KnowledgeGapAnalyzer (CI fast lane)
```

### Run a single pytest test file

```powershell
python -m pytest test_grounding_gate_authority.py -v
python -m pytest test_eval_gate.py -v
```

### Check the promotion gate on a saved report

```powershell
python scripts/check_eval_gate.py reports/run_01.json
python scripts/check_strict_pass.py reports/run_01.json   # also warns on silent killer removal
```

### Aggregate multiple reports

```powershell
python aggregate_reports.py reports/
```

## CI

Two GitHub Actions workflows:

| Workflow | Trigger | Authority |
|---|---|---|
| `eval_strict.yml` | push/PR to `main` | **Authoritative** — required for PROMOTE |
| `eval_dev.yml` | push to non-main branches | Non-authoritative fast feedback, uses `--fast` |

Both workflows run `test_grounding_gate_authority.py` first (lightweight, no Ollama) and validate `tests/eval_queries.json` before the heavier eval job. The strict workflow pins Ollama to digest `500a1f067a9f…` (qwen2:1.5b).

## Eval suite (`tests/eval_queries.json`)

JSON array of query objects. Required fields: `query` or `question`. At least one entry must have `"killer": true` — the gate enforces a hard fail if any killer query does not pass. Do not remove killers silently; `check_strict_pass.py` will warn.

When adding new queries, follow the pattern in existing entries and run the full strict eval before merging.

## Frozen surfaces (v1.0)

Do **not** modify without a reproducible failure case, a before/after strict eval run, and a review note:

- `generation/grounding.py` — cosine threshold (0.60) and overlap floor (≥ 1)
- `generation/llm.py` — system prompt content and structure
- `app/config.py` — `TOP_K`, `CHUNK_SIZE`, `CHUNK_OVERLAP`
- `app/pipeline.py` — retrieval score thresholds and reranker integration
- `evaluation/refusal.py` — keyword list for refusal predicates
- `tests/eval_queries.json` — killer query set

## Corpus and documents

Raw documents live in `data/docs/` and are loaded by `app/ingest.py`. OCR for scanned PDFs uses Tesseract via `scripts/ocr_helper.py` (300 DPI primary, 400 DPI / psm11 fallback). The `evaluation/ocr_check.py` presence check is a fail-closed gate signal.

## Rollback

```powershell
git checkout v1.0-strict-promote
```
