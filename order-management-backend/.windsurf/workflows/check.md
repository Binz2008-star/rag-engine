---
auto_execution_mode: 2
description: Quick health check — git status, typecheck, lint, tests
---

# Check

// turbo

1. Run `git status` and `git rev-parse --short HEAD` and `git branch --show-current`

// turbo 2. Run `npx tsc --noEmit` for typecheck

// turbo 3. Run `npx eslint src/ --max-warnings=999` for lint

// turbo 4. Run `npx vitest run` for tests

5. Report results as a summary table. No fixes, no suggestions. Facts only.
