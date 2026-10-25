# Operations Hardening — Findings

## Existing code paths
- `backend/app/query_cache.py` caches retrieval responses by normalized query and `k`; reports are generated separately, so cached report freshness is not tied to evidence identity.
- `backend/app/services/embedding_service.py` exposes `embed_texts()` and batches cache misses in one Gemini API request; query/retrieval paths mostly call the single-item wrapper.
- `backend/app/core/limiter.py` silently selects `memory://` without Redis. `main.py` has a lifespan check for Supabase but no production Redis requirement.
- `frontend/hooks/useSignalsWS.ts` already uses a single-use WS ticket and exponential reconnect, but `useDashboard.ts` refreshes the Clerk token every 45 seconds and passes it as a dependency, potentially restarting the socket. SWR already polls every 5s only while WS is not `open`.
- `backend/app/services/gemini_client.py` already has provider streaming methods. `/api/generate` currently awaits non-stream generation and returns JSON; frontend `generateInsight` has a text/plain reader, not an SSE parser.
- Main logging is plain text. There is no OpenTelemetry dependency/config, and `/metrics` exposes process counters plus subsystem values. Need inspect precise metric definitions before altering.
- API keys are already SHA-256 hashed, shown once, and owner-scoped, but have no scopes, expiry, or rotate operation. `api_keys` table is created in migration 004; extend with an additive migration.
- `.github/workflows/ci.yml` runs Ruff/MyPy with `|| true`, tests, tsc, Vitest, and build. It has no pip-audit, npm audit, Bandit, gitleaks, or Dependabot config.
- LLM calls occur in query `/generate`, compare, graph simulation, digest, PDF extraction, and ingestion extraction. `GeminiClient` supports both new and legacy SDK, but its non-stream wrapper currently discards response usage metadata; usage/cost instrumentation must be added where provider responses are available.
- Existing `embed_texts()` already batches misses from ingestion and returns positions aligned to input. Compare/retrieval make separate query embeddings; group company query strings before lookup where practicable and add tests that verify one provider batch.
- `main.py`'s `/metrics` currently returns JSON process counters and subsystem stats, not Prometheus text. Preserve that contract and add ingestion lag in the existing response; an OTel exporter can be separate middleware/SDK plumbing.
- `api_keys` currently stores hash/prefix/owner/name/revoked/last-used/created. Auth lookup returns only ID/owner/revoked. UI creates and revokes keys but has no scope/expiry controls; migration 004 is the base schema and tenant migration 007 owns its RLS policy.
- Existing websocket ticket issuance is authenticated and ticket-based. The reconnect effect depends on a token that the dashboard rotates every 45 seconds even though `createSignalsWsTicket()` uses the shared API token getter; keep one socket healthy and rely on ticket refresh only at reconnect.
- The frontend's `generateInsight` reader consumes `text/plain`; the backend already has a Gemini async stream method but no SSE contract. Implement an explicit SSE path and retain the JSON response for older clients.
- CI currently marks Ruff, MyPy, and ESLint non-blocking with `|| true`; security gates should be required steps. `backend/requirements.txt` is the pip audit input, and `frontend/package-lock.json` is the npm audit input.
- Existing tests include focused API-key, WebSocket, report validation, and frontend WS hook coverage; extend those rather than introducing new test harnesses.
- Available Redis helper `create_redis_client(required=True)` already pings Redis and is used by the scheduler worker. Reuse or factor it so rate limiting and budget startup validation share the same config semantics.
- The report generation endpoint returns a Pydantic JSON response; the frontend API helper has a `text/plain` compatibility branch that never matches the backend response. Add `Accept: text/event-stream` opt-in and retain JSON for old clients.

## Decisions / assumptions to validate during implementation
- Use Redis atomic counters for shared daily token budgets and user quotas; when Redis is unavailable in production, reject new LLM work and report degraded behavior.
- Report cache entries are keyed by normalized query and a deterministic hash of grounded evidence plus graph context; use a bounded process-local TTL cache because the request requires no cross-instance persistence for generated reports.
- Gemini billing rates are configurable by model/env because pricing changes; log tokens and latency regardless, and log cost estimate only when rate config exists.
- SSE response emits report deltas only after complete schema validation and evidence grounding; streaming is over the network/UI after validation, trading first-byte latency for report trustworthiness.
- API-key scopes are explicit route capabilities; existing keys receive backward-compatible read/generate scopes and a 90-day transition expiry in migration 009.
- Dependabot configuration uses GitHub Actions, pip, and npm ecosystems on a weekly schedule; dependency audit gates high/critical severity and secrets scan has no suppression without documented false positive.
- Chroma 1.5.9 requires OpenTelemetry components compatible with the installed 1.41 series; older 1.30 pins broke Chroma telemetry imports in tests. Keep OTel packages on the 1.41.1 / 0.62b1 matching pair.
- `npm audit` initially reported high/critical findings. Compatible lockfile updates and a Vitest 5.0.5 upgrade resolved them without changing the test API; `npm audit --audit-level=high` is now clean.
- The Python audit still reports existing high-severity vulnerabilities among the pinned and transitive dependencies. CI preserves the pip-audit JSON output and uses OSV CVSS scores to fail at 7.0 or higher; that inventory remains a remediation item.
- Existing API keys receive a 90-day transition window from migration time, while newly created and rotated keys get a 90-day expiry by default. API-key credentials are deliberately excluded from `keys:manage` so management stays on the authenticated user session.
