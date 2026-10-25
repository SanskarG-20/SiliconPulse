# Security hardening findings

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
- WebSockets use 60-second, hashed, atomically consumed SQLite tickets. API keys are header-only. The frontend obtains a ticket before opening the socket.
- Metrics now requires authentication. Public comment reads/writes are limited, and comment bodies are normalized and stripped of markup/control characters.
- Full verification: backend pytest 136 passed (11 dependency/runtime warnings), TypeScript passed, Vitest 25 passed, Vite production build passed, and `git diff --check` passed.
- Assumptions: the privileged injection role defaults to `admin` and can be changed with `PRIVILEGED_INJECT_ROLE`; RLS migration 007 must be deployed; WebSocket ticket storage relies on a shared SQLite database across backend instances.
