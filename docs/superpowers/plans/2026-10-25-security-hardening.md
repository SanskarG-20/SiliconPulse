# SiliconPulse Security Hardening Implementation Plan

> **For agentic workers:** Execute task-by-task, keeping each security boundary independently testable.

**Goal:** Fix the five requested security areas with shared controls and regression coverage.

**Architecture:** Add a centralized async safe-fetch layer for user-controlled URLs; treat retrieved text as quoted data and accept only strictly validated structured LLM reports; replace URL-carried credentials with headers and one-time WebSocket tickets; enforce Supabase tenant ownership in backend code and RLS; protect metrics and add abuse controls to public comments.

**Tech Stack:** FastAPI, httpx, Pydantic, PyJWT/Clerk, Supabase PostgREST and SQL migrations, React 19/TypeScript, pytest, Vitest, Vite.

**Spec:** User request dated 2026-10-25.

## Global Constraints
- Make minimal, backward-compatible changes except where the requested security boundary requires a behavior change.
- Add regression tests for every changed boundary.
- Run `pytest`, TypeScript typecheck, Vitest, and frontend production build before finishing.
- Fail closed for privileged injection and cross-tenant access.
- Preserve untracked runtime data.

---

### Task 1: Safe outbound fetching

**Files:** `backend/app/services/safe_fetch.py`, RSS and webhook services/routes, corresponding backend tests.

- [ ] Resolve all A/AAAA answers before connecting; reject any private, loopback, link-local, multicast, reserved, unspecified, or metadata-service address.
- [ ] Pin/verify resolved addresses across connection establishment to prevent DNS rebinding; validate each redirect target and limit redirect count.
- [ ] Enforce timeouts, byte ceiling while streaming, and an explicit content-type allowlist.
- [ ] Route user-provided RSS URLs, webhook URLs, tests, and delivery through this helper.
- [ ] Add mocked DNS/transport tests for blocked addresses, redirect rebinding, content type, response-size overflow, and timeout.

### Task 2: Prompt injection and privileged manual injection

**Files:** report generation and prompt construction, `/api/inject` auth policy, tests.

- [ ] Put evidence in explicit untrusted-data framing and state the instruction hierarchy in the system prompt.
- [ ] Require a strict Pydantic JSON report schema, parse model output, and reject malformed/extra/nonconforming fields.
- [ ] Ensure RSS, fetched news, PDF, and manual injection text enter only as evidence data.
- [ ] Require a configured privileged role claim for `/api/inject`; absent/unknown claims deny.
- [ ] Test prompt framing, strict schema rejection, and role allow/deny behavior.

### Task 3: Credential transport and WebSocket tickets

**Files:** `backend/app/core/auth.py`, auth/WebSocket routes, `backend/app/ws.py`, `frontend/api/siliconpulseApi.ts`, `frontend/hooks/useSignalsWS.ts`, tests.

- [ ] Remove query-string API-key extraction and test rejection.
- [ ] Issue opaque WebSocket tickets from a bearer-authenticated endpoint; store hashed tickets with expiry and atomic single-use redemption.
- [ ] WebSocket accepts tickets only, not JWTs; frontend fetches ticket with authenticated API client and sends ticket in URL.
- [ ] Test expiry, reuse, invalid ticket, and JWT/query token rejection.

### Task 4: Tenant authorization and RLS

**Files:** Supabase query helper/dependency, affected routes and client operations, new migration, authorization tests.

- [ ] Inventory every Supabase query for workspaces, briefs, watchlists, history, and API keys; identify owner/member columns and public-share exceptions.
- [ ] Centralize authenticated-user ownership/member checks; scope all reads and writes by verified user/workspace membership, failing closed on errors.
- [ ] Add matching RLS policies as defense in depth without relying on RLS for service-role requests.
- [ ] Test cross-tenant read/mutation denial for each resource family and public brief/comment exceptions.

### Task 5: Metrics and public comments

**Files:** `backend/app/main.py`, comment routes/schema/sanitization, abuse controls, tests.

- [ ] Protect `/metrics` with auth or network restriction; preserve a documented operational scrape mechanism.
- [ ] Sanitize comment text, bound payload size, and add rate limits/abuse controls to public comment endpoints.
- [ ] Test unauthenticated metrics denial and comment sanitization/rate limiting.

### Task 6: Full verification and review

- [ ] Run backend `pytest`.
- [ ] Run frontend TypeScript check (`npx tsc --noEmit`).
- [ ] Run Vitest.
- [ ] Run frontend production build.
- [ ] Review diff and confirm no unrequested runtime files changed; document residual risks.
