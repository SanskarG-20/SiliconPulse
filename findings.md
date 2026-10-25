# Security hardening findings

# Reliability hardening findings (2026-10-25)

## Actual datastore and job usage
- Pathway is not installed (`pathway==0.11.0` is commented out), but Compose starts `pathway_pipeline.py`; `safe_read_jsonl` conditionally reads `pathway_out.jsonl`. This is a broken optional path that can select stale derived data, not an operational pipeline.
- JSONL is the global signal source read by retrieval, trend, feed, WebSocket, recommendations, and alerts; ingestion appends to it.
- SQLite (`DB_PATH`) stores `seen_events`, `source_checkpoints`, and WebSocket tickets. Chroma stores local vectors. Supabase/Postgres stores user data and `signals_vec`; `vector_store.py` currently falls back to Chroma when pgvector fails.
- Redis is used for pub/sub, queueing, and optional rate limiting. It is not the canonical signal store.
- `main.py` starts APScheduler in every web process, including Render. Docker Compose also defines a separate distributed worker, but it does not run the scheduled ingestion/digest jobs. A missing APScheduler fallback loop is also launched in-process.
- Ingestion has some source checkpoints and event dedup, but checkpoint metadata is SQLite-only and scheduler intervals do not catch up after downtime. Digest polling selects only the exact current UTC hour, so a missed hour is lost.

## Selected implementation approach
- Remove the currently non-operational Pathway integration and use the canonical signal-store interface; keep platform-neutral classification already in the regular ingestion path.
- Supabase `market_signals` and pgvector become the canonical production signal/embedding/checkpoint/ticket store. JSONL, SQLite, and Chroma remain development fallback/caches; production configuration fails fast without Supabase.
- Add an idempotent migration utility for legacy JSONL events, SQLite checkpoints, and Chroma embeddings. Dedup state is rebuilt from canonical event IDs; expired WS tickets are intentionally not migrated.
- Run APScheduler only via a dedicated module/process. Require Redis in production and use renewed per-job locks. Start pull/check jobs immediately after startup, use persisted checkpoints/lookbacks, and include missed daily digest hours in catch-up selection.
- Digest external delivery can be retried after an ambiguous provider response; provider-side idempotency is not available consistently across the configured email and webhook channels.

## Initial repository state
- User explicitly requested security fixes, regression tests, and full backend/frontend verification.
- No `AGENTS.md` guidance was found in the earlier repository inventory.
- Existing untracked paths: `backend/data/stream.jsonl.bak` and `data/chroma/`; preserve them.
- Stack and route map from prior inspection: FastAPI routers under `backend/app/routes`, Clerk/API-key auth in `backend/app/core/auth.py`, Supabase service-role client in `backend/app/supabase_client.py`, React API client in `frontend/api/siliconpulseApi.ts`.

## Detailed inspection
- `backend/app/sources/rss_source.py` previously performed `httpx` GETs with automatic redirects and no streamed response-size cap; `digest_service.send_slack` posted directly to webhook URLs. Slack/Discord validation used string prefixes.
- Personal Supabase reads/writes for watchlists, history, briefs, and API keys filter by `user_id`. Workspace routes gate workspace-id reads/mutations by membership; public brief reads/comments gate `is_public`. The service-role client bypasses RLS, so backend checks remain necessary.
- API keys were accepted from both `X-API-Key` and `?api_key=`. WebSocket auth decoded Clerk JWTs from `?token=`.
- `/metrics` had no auth dependency. Comment writes had a 20/minute IP limit and 2,000-character bound but no content sanitization; comment reads had no route rate limit.
- Gemini report generation streamed text before validation. PDF extraction parsed model JSON leniently. `InsightReport` allowed arbitrary section ids and extra fields.
- Migration 007 adds direct-client policies for tenant tables and removes direct workspace membership writes. Workspace membership is checked by a shared `TenantAccess` dependency in workspace/brief routes.
- `safe_fetch` now resolves destinations, rejects non-public IP answers, connects to the chosen validated IP, manually revalidates redirects, enforces timeout/content-type/response-size caps, and is used by RSS and Slack/Discord delivery.
- Retrieved/document content is JSON-encoded and delimiter-framed as untrusted data; Gemini report and PDF extraction output is schema-validated. `/api/inject` requires the configured role (`PRIVILEGED_INJECT_ROLE`, default `admin`).
- WebSockets use 60-second, hashed, atomically consumed Supabase tickets in hosted deployments and SQLite tickets only in local development. API keys are header-only. The frontend obtains a ticket before opening the socket.
- Metrics now requires authentication. Public comment reads/writes are limited, and comment bodies are normalized and stripped of markup/control characters.
- Full verification: backend pytest 136 passed (11 dependency/runtime warnings), TypeScript passed, Vitest 25 passed, Vite production build passed, and `git diff --check` passed.
- Assumptions: the privileged injection role defaults to `admin` and can be changed with `PRIVILEGED_INJECT_ROLE`; RLS migration 007 and reliability migration 008 must be deployed. WebSocket tickets and ingestion checkpoints use Supabase in production.
