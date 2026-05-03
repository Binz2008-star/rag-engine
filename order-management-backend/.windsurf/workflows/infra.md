---
description: Diagnose environment/test harness issues — classify failures before fixing
---

# Infra

Scope: Diagnose failures caused by environment or infrastructure, not application logic.

1. Run `npx vitest run 2>&1` and collect failing tests.

2. For each failure, classify as one of:
   - **infra issue** — missing external service (DB, Redis, server not running)
   - **test harness issue** — test assumes running server, wrong import, setup ordering
   - **code-level infra bug** — module initialization, import side effects, lazy-init missing
   - **actual code defect** — logic error in domain/service layer

3. Return ONLY:
   - failing test name
   - classification
   - root cause (1 line)
   - minimal fix direction (1 line)

Rules:
- Do NOT modify code
- Do NOT refactor
- Do NOT guess
- Focus on runtime behavior only
- If a failure is caused by missing external service (DB, Redis, server) -> classify as INFRA, not code defect
