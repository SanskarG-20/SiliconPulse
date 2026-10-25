# Security hardening task plan

## Goal
Fix the five requested security areas with centralized URL fetching, untrusted-prompt handling and schema validation, header-only API keys and one-time WebSocket tickets, code-enforced tenant ownership plus RLS, and protected metrics/comments.

## Phases

- [x] 1. Trace existing code, settings, database migrations, and tests for each affected surface.
- [x] 2. Implement one SSRF-safe fetch helper; route RSS pulls, webhook delivery, and webhook tests through it; add focused tests.
- [x] 3. Harden report generation and injection authorization; add focused tests.
- [x] 4. Remove API keys from query strings and replace JWT-in-WebSocket-URL with short-lived single-use tickets; add focused tests.
- [x] 5. Audit tenant-scoped Supabase access, enforce ownership through shared auth helpers/dependencies, add RLS migrations, and add fail-closed cross-tenant tests.
- [x] 6. Protect metrics and sanitize/rate-limit public comments; add focused tests.
- [x] 7. Run full requested checks: backend pytest, frontend tsc, Vitest, production build; review final diff and residual risks.

## Constraints and assumptions

- Preserve existing request/response behavior except where a listed security requirement explicitly changes it.
- `X-API-Key` remains supported; `?api_key=` is rejected.
- WebSocket clients must first obtain an opaque, short-lived ticket using their authenticated session, then redeem it once at the WebSocket endpoint.
- The `/api/inject` privileged role must be explicit and deny-by-default; review existing role claims/configuration before choosing the claim shape.
- Tenant authorization must fail closed when Supabase is unavailable or ownership cannot be established.
- Keep existing user data and unrelated untracked files untouched.
- Add regression tests for each changed security boundary.

## Risks to resolve during inspection

- There may be legacy Supabase tables without a reliable tenant/owner column; establish exact schema before changing queries.
- Some existing public routes may be deliberately unauthenticated; preserve their public access while validating ownership for mutations.
- Existing outbound services (including Gemini/news providers) use URLs that are not user-controlled; restrict the shared SSRF helper to user-supplied destinations.

## Next Step
Implementation and verification are complete. Apply migration `007_tenant_access_hardening.sql` in the Supabase environment before relying on its direct-client RLS defense.

## Errors Encountered
| Error | Attempt | Resolution |
|---|---:|---|
