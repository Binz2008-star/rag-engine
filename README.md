# RAG Assistant

Local-first assistant platform built around a grounded RAG pipeline, with capability shells for trading analysis and agent analysis.

## Current capabilities

### 1. RAG
Document-grounded question answering using the evaluated pipeline.

- Endpoint: `POST /api/query`
- UI: supported
- Contract: grounded-only
- Refusal behavior: returns `Insufficient data.` when grounding fails or data is unavailable

### 2. Trading analysis shell
Structured classification layer for trading-related prompts.

- Endpoint: `POST /api/trading/analyze`
- UI: supported
- Current scope: analysis shell only
- Not implemented: live signals, execution, broker integration, backtesting engine

### 3. Agent analysis shell
Structured classification layer for planning, scheduling, task, and memory-oriented prompts.

- Endpoint: `POST /api/agent/analyze`
- UI: supported
- Current scope: analysis shell only
- Not implemented: persistent task execution, scheduler engine, autonomous workflows

### 4. System health
Operational health visibility for backend dependencies.

- Endpoints:
  - `GET /api/health`
  - `GET /api/system/health`

### 5. Agent Runtime
Foundational services for task management, scheduling, and execution.

- **TaskStore**: Thread-safe in-memory task store with JSON persistence
- **SchedulerService**: Simple scheduler for scheduling tasks
- **AgentExecutor**: Shell for executing agent tasks

API Endpoints:
- POST /api/agent/tasks - Create a new agent task
- GET /api/agent/tasks?session_id=... - List agent tasks
- POST /api/agent/tasks/schedule - Schedule a task
- POST /api/agent/tasks/execute - Execute a task

## Architecture overview

- **Backend:** FastAPI
- **Frontend:** Next.js
- **LLM runtime:** Ollama
- **Embedding model:** `nomic-embed-text`
- **Chat / answer model:** configured through environment
- **Retrieval:** local vector/index pipeline
- **Capability shells:** RAG, Trading, Agent

## Local run

### Backend
```bash
cd D:\AI\assistant
python -m uvicorn server.main:app --reload --host 0.0.0.0 --port 8000 --app-dir api
```

### Frontend

```bash
cd D:\AI\assistant\frontend
npm install
npm run dev
```

## Required local services

### Ollama

Ollama must be running locally before backend startup.

Typical local endpoint:

```text
http://localhost:11434
```

Required models:

* embedding model: `nomic-embed-text`
* chat model: configured in environment (`CHAT_MODEL`)

## Frontend behavior

The frontend currently supports three user-facing paths:

* document / RAG questions
* trading analysis prompts
* agent analysis prompts

The current UI routes requests using prompt classification logic and renders:

* normal text answers for RAG
* structured cards for trading analysis
* structured cards for agent analysis

## Streaming note

The system includes a buffered streaming path for RAG responses.

Important:

* streaming is policy-safe
* the client does **not** receive ungrounded partial output
* tokens are emitted only after validation succeeds
* this is validated progressive rendering, not raw low-latency speculative streaming

## Reliability hardening

Embedding calls were hardened with:

* warm-up on startup
* `keep_alive` on embedding requests
* improved retry behavior
* better logging for embed failures

This was added to reduce intermittent Ollama embedding failures and model unload/reload instability.

## Known limitations

### Trading

* no market data integration
* no execution engine
* no risk engine
* no persistent strategy state

### Agent

* no scheduler implementation yet
* no persistent task store yet
* no executor runtime yet
* no tool orchestration loop yet

### Routing

Current frontend routing still uses client-side keyword detection. This should be replaced by backend-first dispatch in a later phase.

## Development status

This branch introduces:

* capability shells
* frontend cards for trading and agent flows
* system health reporting
* context, logging, capability routing, and guardian services
* embedding hardening
* policy-safe buffered streaming support

It is a substantial platform step, but not the final production architecture.
