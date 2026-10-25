# Reliability Hardening Implementation Plan

> **For agentic workers:** Execute this plan inline task by task and run each task's listed regression tests.

**Goal:** Make Supabase/Postgres the production source of truth, remove the broken unused Pathway path, and run catch-up capable scheduled jobs in one separately locked worker process.

**Architecture:** A canonical signal repository reads/writes `market_signals` and Postgres operational tables when Supabase is configured; local JSONL/SQLite/Chroma remain only for development. A dedicated APScheduler entrypoint runs under a renewed Redis lock for each job. Startup executes due ingestion/digest checks, while stable event IDs and persisted checkpoints make ingestion resumable.

**Tech Stack:** FastAPI, Supabase PostgREST/RPC, pgvector, SQLite and Chroma for local dev, APScheduler, redis-py, Docker Compose, Render Blueprint, pytest.

**Spec:** User request in the SiliconPulse reliability-hardening task on 2026-10-25.

## Global Constraints
- Do not remove local development usability when Supabase is absent.
- Fail production startup without Supabase/Postgres and a Redis lock backend.
- Preserve API response shapes and current ingestion IDs.
- Importer must be idempotent and support dry-run/reporting.
- Do not delete existing local datasets.

---

### Task 1: Remove broken Pathway integration

Remove the dependency-less Compose service, alternate JSONL reader, unused sharded runner, mock scripts, stale docs/settings, and Pathway-only test. Keep existing company/event classification in ordinary ingestion.

### Task 2: Canonical Postgres signal and operational storage

Add a Supabase migration for `market_signals`, persisted source checkpoints, and WebSocket tickets plus RPCs for atomic signal ingestion, bounded reads, and single-use ticket redemption. Route `safe_read_jsonl`, `deduplicate_and_append`, storage helpers, and metrics through Postgres when enabled. Make pgvector authoritative and prohibit Chroma fallback in configured production; retain local stores only when Supabase is absent in development.

### Task 3: Idempotent local-data importer

Add a CLI that reads JSONL events, SQLite checkpoints, and Chroma vectors in bounded batches, calls the production repository upserts, supports `--dry-run`, and does not import short-lived tickets or derived dedup rows. Test repeat execution and malformed input handling with mocked Supabase/Chroma.

### Task 4: Dedicated scheduler process and distributed locking

Remove scheduler lifecycle from FastAPI startup. Add a `python -m app.scheduler_worker` entrypoint, compose service, and Render background worker. Add renewable per-job Redis locks; production worker startup fails if Redis is missing or unreachable, while local development can use process-local locks. Use APScheduler single-instance/coalescing settings.

### Task 5: Catch-up and idempotency

Run due ingestion immediately at worker start, persist GDELT/HackerNews checkpoints in Postgres, query bounded source lookback windows, and make signal insertion conflict-safe. Make digest due selection include elapsed configured UTC hours since the last successful daily send and update the marker only after at least one delivery succeeds. Cover stale startup, duplicate ticks, and retry behavior.

### Task 6: Documentation and verification

Document each datastore's role, local-cache behavior, migration steps, worker deployment requirements, lock behavior, and digest retry limitation. Run full backend pytest, frontend typecheck/Vitest/build, and review all remaining references to removed pathways and production local-disk writes.
