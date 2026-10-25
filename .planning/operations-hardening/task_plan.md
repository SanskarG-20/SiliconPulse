# Operations Hardening — Task Plan

## Goal
Implement the seven operations hardening requirements from the current user request and verify each one.

## Phases
- [x] 1. Evidence-aware report caching, batched embeddings, per-user quotas, global daily LLM budget.
- [x] 2. Redis-required production rate limiting, in-memory development fallback.
- [x] 3. WebSocket-primary feed with bounded reconnect and SWR polling only on unhealthy WS.
- [x] 4. SSE report delivery with schema and grounding validation before text is exposed.
- [x] 5. JSON logs, request IDs, OpenTelemetry, LLM usage/cost/latency, ingestion lag alert metric.
- [x] 6. API key scopes, expiry, and rotation with one-time plaintext display.
- [x] 7. CI dependency/security/secrets scanners and Dependabot.
- [x] 8. Full backend/frontend verification, final diff review, commit.

## Constraints
- Preserve compatibility wherever the request allows it.
- Add regression coverage for each behavior change.
- Production Redis is mandatory for request limiting and shared budgets; local in-memory paths are dev-only.
- Do not stream unvalidated report claims.
- Keep API key plaintext out of logs/storage and show it only once.

## Next Step
Run final full backend/frontend checks, review the complete diff and commit the changes.

## Phase 0 — Inspection
- [x] Read previous plan/findings/progress and confirm clean worktree.
- [x] Map cache, embedding, limiter, WebSocket/SWR, report stream, API keys, metrics/logging, CI, and SQL migration files.
- [x] Record assumptions and tradeoffs in the implementation plan.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
