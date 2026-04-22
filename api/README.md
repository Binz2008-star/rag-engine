# API Overview

## Base URL
Local development default:

```text
http://localhost:8000
```

## Endpoints

### `POST /api/query`

Grounded RAG question answering.

#### Request

```json
{
  "question": "What does ECO do?",
  "session_id": "s1",
  "user_id": "u1"
}
```

#### Response

```json
{
  "answer": "string",
  "sources": [
    {
      "source": "string",
      "chunk_id": "string",
      "doc_type": "string",
      "score": 0.0
    }
  ],
  "latency_ms": 0,
  "wall_ms": 0,
  "request_id": "string",
  "intent": "string",
  "intent_confidence": 0.0,
  "intent_method": "string",
  "intent_method_raw": "string",
  "grounded": true,
  "failure_type": null,
  "model_version": "string",
  "retriever_version": "string"
}
```

### `POST /api/trading/analyze`

Trading analysis shell endpoint.

#### Request

```json
{
  "question": "Analyze EURUSD on H1",
  "session_id": "s1",
  "user_id": "u1"
}
```

#### Response

```json
{
  "capability": "trading",
  "intent": "analyze",
  "market": "forex",
  "asset": "EURUSD",
  "timeframe": "H1",
  "prompt": "Analyze EURUSD on H1",
  "status": "accepted"
}
```

### `POST /api/agent/analyze`

Agent analysis shell endpoint.

#### Request

```json
{
  "question": "Create a plan to add scheduled task support",
  "session_id": "s1",
  "user_id": "u1"
}
```

#### Response

```json
{
  "capability": "agent",
  "intent": "plan",
  "prompt": "Create a plan to add scheduled task support",
  "summary": "This request looks like a planning or orchestration request.",
  "suggested_tools": ["planner", "capability_router"],
  "status": "accepted"
}
```

### `GET /api/health`

Basic service readiness.

### `GET /api/system/health`

Extended dependency and service health report.

## Buffered streaming

The RAG API includes a policy-safe buffered streaming path.

Design constraints:

* canonical RAG behavior remains authoritative
* no ungrounded partial output is sent to the client
* tokens are emitted only after validation succeeds

This preserves grounded-only product behavior while still allowing streamed rendering after validation.

## Service modules added

* `context_service.py`
* `interaction_log_service.py`
* `capability_router.py`
* `health_guardian.py`
* `trading_service.py`
* `agent_service.py`

## Important boundaries

### RAG

* real answer path
* grounded-only
* refusal-aware

### Trading

* shell only
* classification only
* no execution

### Agent

* shell only
* classification only
* no autonomous runtime yet
