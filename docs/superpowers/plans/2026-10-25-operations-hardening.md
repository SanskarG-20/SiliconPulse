# Operations Hardening Implementation Plan

> **For agentic workers:** Use the ordered phases below. Each phase has an isolated implementation and verification pass before the next phase.

**Goal:** Harden SiliconPulse runtime operations across LLM spend, request limiting, realtime delivery, streamed reports, telemetry, API-key lifecycle, and supply-chain CI.

**Architecture:** Reuse the existing Redis, FastAPI, Gemini streaming, Supabase, WebSocket, and SWR foundations. Add shared quota/cache/telemetry services and keep local-only fallbacks explicit. Preserve existing JSON API behavior where possible; add opt-in/compatible SSE negotiation and new API-key fields without returning stored secrets.

**Tech Stack:** FastAPI/Python 3.11, Redis, Supabase/Postgres, Gemini SDK, React 19/SWR, SSE, OpenTelemetry, GitHub Actions.

**Spec:** User request in the current Codex task (7 hardening requirements).

## Global constraints

- Read affected paths before changes; keep diffs minimal and backward compatible.
- Add regression tests for every behavior change.
- Run backend pytest, frontend TypeScript, Vitest, and production build before finishing.
- Production rate limiting must fail startup without Redis; memory storage remains development-only.
- LLM budgets fail closed for new model calls and degrade to evidence-only output.
- Stream only schema-validated, grounded report output to the browser.
- API keys remain hash-only in storage; new plaintext is returned once.
- Security scanners fail CI on high/critical findings; secrets scanning blocks detected credentials.

## Ordered phases

1. **Report and embedding cache / LLM quotas:** key report cache by normalized query plus evidence hash, keep TTL; batch embeddings; add per-user daily call/token quotas and a shared Redis daily token budget with fallback responses. Test cache invalidation, quotas, atomic budget consumption, and batch alignment.
2. **Production rate-limit startup:** derive backend environment consistently, validate Redis configuration and connectivity before serving in production, retain memory limiter only in development. Test startup validation and dev fallback.
3. **Realtime primary path:** audit existing WebSocket and SWR integration, eliminate reconnect churn caused by periodic token refresh, maintain bounded exponential reconnect and pause polling only while WS is healthy. Test WS state, fallback timing, and no duplicate refresh when open.
4. **Validated SSE reports:** expose an SSE media-type path for report generation, buffer/validate/ground the final JSON before emitting report deltas, keep the legacy JSON endpoint contract available. Test event framing, validation failures, disconnect cleanup, and frontend parsing.
5. **Observability:** configure JSON logs and request ID propagation; instrument FastAPI and Gemini calls with OpenTelemetry; record provider usage, estimated/configured cost, latency, and failures; expose ingestion lag and threshold alerts. Test serializers, trace/request IDs, metric updates, and alert threshold.
6. **API-key lifecycle:** add scopes and expiry checks to auth, support scoped creation, rotation (new key once and revoke prior key atomically where possible), and safe ownership filtering; deploy additive schema migration. Test hash-only persistence, scope enforcement, expiry, rotation, and fail-closed behavior.
7. **CI supply-chain gates:** add pip-audit, npm audit high severity, Bandit, gitleaks, and Dependabot configuration. Validate workflow syntax and run locally available scanners where possible.

## Review notes / tradeoffs

- A report cache uses evidence identity so newly ingested evidence cannot reuse stale reports; results remain user-scoped at quota boundaries.
- Cost estimates require configured per-model rates because Gemini pricing can change; usage tokens and latency are still logged when rates are absent.
- SSE only publishes validated, grounded text, so first visible report bytes arrive after Gemini completes. This protects consumers from seeing claims later rejected by schema/grounding checks.
- Redis is a production hard dependency for both request limiting and shared LLM budgets; deployment must provision it before production rollout.
- API-key rotation must not claim atomicity if Supabase exposes only separate REST calls; overlapping key validity is capped and documented if a transactional RPC is unavailable.

## Verification record

- To be filled by the implementation pass with per-phase tests and final full-suite results.
