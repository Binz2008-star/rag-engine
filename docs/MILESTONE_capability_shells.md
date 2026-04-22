# Milestone: Capability Shells + UI Hardening

## Shipped

### Backend
- context service
- interaction log service
- capability router
- health guardian
- trading analysis service shell
- agent analysis service shell
- system health endpoint
- embedding warmup and keep_alive hardening
- buffered, policy-safe streaming support

### Frontend
- chat shell usability improvements
- trading analysis card
- agent analysis card
- local dev CORS compatibility
- stable routing for RAG, trading, and agent UI flows

## Verified
- `POST /api/query`
- `POST /api/trading/analyze`
- `POST /api/agent/analyze`
- `GET /api/health`
- `GET /api/system/health`

## Important design decisions

### 1. Grounded-only invariant preserved
The RAG path remains grounded-only.

### 2. Streaming is buffered, not speculative
Streaming was implemented in a policy-safe way:
- generate
- validate
- then emit tokens

This avoids show-then-retract behavior.

### 3. Trading is a shell, not an execution engine
No live trading or broker integration exists yet.

### 4. Agent is a shell, not an autonomous runtime
No scheduler, task persistence, executor loop, or memory runtime exists yet beyond current context/logging foundations.

### 5. Embedding stability was hardened
Warmup and keep_alive were added to reduce intermittent Ollama embedding failures.

## Not shipped yet

### Trading
- live market feeds
- execution engine
- risk engine
- persistent analysis history
- strategy runtime

### Agent
- persistent task store
- scheduler
- executor
- tool runtime
- backend-first dispatch
- autonomous workflow lifecycle

### Frontend
- backend-first dispatch instead of client keyword routing
- richer source rendering
- system health UI
- session persistence beyond static local IDs

## Recommended next phase
Phase 7:
- remove client-side keyword routing
- add backend-first dispatch endpoint
- return capability-tagged responses from one backend entrypoint
