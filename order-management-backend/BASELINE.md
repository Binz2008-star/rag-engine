# Canonical Baseline

## State

| Field | Value |
|-------|-------|
| **Branch** | `feat/l1-verification-infrastructure` |
| **HEAD** | `bba1848` |
| **Date** | 2026-04-11 |
| **Working tree** | Clean (2 intentionally untracked: `packages/sdk/`, `src/tests/contract/launch.json`) |

## Commits in this session (on top of main)

1. `5acb89f` — Baseline consolidation: env hardening, authority pattern, test factories, env guards
2. `a6d5eb8` — Typecheck fixes: REDIS_URL optional chaining, vitest import, NODE_ENV readonly, remove @vercel/analytics
3. `bba1848` — Critical fixes: remove duplicate order creation path, mock ID map, SQLite fallback

## Gate Results

| Gate | Result |
|------|--------|
| **Typecheck** | ✅ PASS — 0 errors |
| **Lint (src/)** | ⚠️ 95 pre-existing errors (80 `no-explicit-any`, 10 fetch restriction, 5 misc) |
| **Tests** | 86 passed, 9 skipped, 4 failed |

### Failing tests (all pre-existing, not introduced by this session)

| Test | Root Cause |
|------|-----------|
| `production-hardening.test.ts` (suite crash) | `rate-limiter.ts` triggers Redis init at import time |
| `order.contract.test.ts` | Integration test — requires running server (ECONNREFUSED) |
| `cross-repo.contract.test.ts` (4 tests) | Integration test — requires running server (ECONNREFUSED) |

## Critical Findings Fixed

1. **Duplicate order creation path** — `/api/seller/orders` POST removed (was bypassing authority pattern, no event emission, zero-value totals)
2. **Mock external ID map** — Hardcoded `MOCK_EXTERNAL_ID_MAP` removed from `v1-order.authority.ts`. IDs accepted directly.
3. **SQLite fallback** — `prisma-client.ts` no longer falls back to `file:./dev.db`. Fails fast if `DATABASE_URL` is unset.

## Remaining Known Issues (documented, not blocking)

### Medium priority
- `seller/orders/route.ts` GET still uses inline Prisma query (not through `order-list.query.ts`)
- Test files (`order.test.ts`, `payment-confirm.test.ts`, etc.) still use direct Prisma instead of factories
- `env-guard.ts` defaults to `'development'` when env vars are unset (should arguably fail)
- Pricing is placeholder ($10/item, $5 delivery) — needs platform catalog integration

### Low priority
- 80 `no-explicit-any` lint errors across codebase
- 4 worktree-bound branches still exist (cannot delete from this worktree)
- 2 stashes from old branches still present
- OpenAPI docs still reference `seller_123`/`customer_456` example IDs

## Branch Cleanup

| Action | Count |
|--------|-------|
| Branches deleted | 6 |
| Branches remaining (worktree-bound) | 4 |
| Current local branches | 6 (including main + current) |

## Next Steps

1. Merge `feat/l1-verification-infrastructure` → `main`
2. Fix `production-hardening.test.ts` import ordering issue
3. Migrate remaining inline queries to authority/query modules
4. Migrate test setup to use factories
5. Address `no-explicit-any` lint errors
6. Integrate real pricing from platform catalog
