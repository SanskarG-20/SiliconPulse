# SiliconPulse

**Real-time strategic intelligence for the semiconductor and AI supply chain.**

SiliconPulse ingests live market signals, deduplicates and enriches them, and uses Google Gemini to synthesize evidence-backed executive briefings with supply-chain graph context. Hybrid keyword + vector retrieval, source verification, and a live React dashboard give operators a tactical view of what changed, why it matters, and what to watch next.

![Status](https://img.shields.io/badge/status-active-success) ![Python](https://img.shields.io/badge/python-3.11-blue) ![Node](https://img.shields.io/badge/node-20-green) ![License](https://img.shields.io/badge/license-MIT-lightgrey)

---

## Table of Contents

- [Overview](#overview)
- [Key Features](#key-features)
- [Architecture](#architecture)
- [Tech Stack](#tech-stack)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Environment Configuration](#environment-configuration)
- [Running Locally](#running-locally)
- [API Documentation](#api-documentation)
- [Project Structure](#project-structure)
- [Data & Ingestion Flow](#data--ingestion-flow)
- [Vector & LLM Flow](#vector--llm-flow)
- [Testing](#testing)
- [CI/CD](#cicd)
- [Deployment](#deployment)
- [Security Considerations](#security-considerations)
- [Troubleshooting](#troubleshooting)
- [Roadmap](#roadmap)
- [Contributing](#contributing)
- [License](#license)

---

## Overview

SiliconPulse is a full-stack intelligence engine:

* **Backend** — FastAPI + APScheduler + SQLite + optional Pathway streaming. Auth via Clerk JWT (`PyJWT` + JWKS), rate-limited, observable (`/health`, `/ping`, `/metrics`).
* **Ingestion** — Free sources (GDELT, HackerNews/Algolia, NewsAPI) + SEC 8-K via Finnhub + PDF uploads (PyMuPDF + optional Gemini vision) → LLM extraction → deduplication → vector index.
* **Intelligence** — Hybrid retrieval (keyword alias expansion + `gemini-embedding-001` / 768-dim cosine ≥ 0.72) → Graph RAG enrichment (supply-chain DAG) → Gemini synthesis → structured JSON report.
* **Frontend** — React 19 + Vite 6 + Tailwind + Clerk + SWR + WebSocket. Manual signal injection, scenario simulation, and export (Markdown/JSON/Text).

The system degrades gracefully when keys are missing: Gemini calls return simulation/fallback reports, vector search falls back to keyword-only, and Supabase/Chroma both have no-op paths.

---

## Key Features

* **Live signal pipeline** — JSONL stream (`data/stream.jsonl`) with SHA-256 dedup via SQLite (`data/siliconpulse.db`), 12-hour freshness window, configurable scan limit (500 events).
* **Hybrid search** — Vector top-30 (Supabase `pgvector` → Chroma fallback) merged with keyword alias hits; vector hits gated at cosine similarity ≥ 0.72.
* **Graph RAG** — 19-edge in-memory DAG (ASML → TSMC → NVIDIA → Microsoft etc.). BFS `get_impact` / `get_suppliers` up to depth 3, weight-product scoring, and `simulate_scenario` shock propagation (`POST /api/graph/simulate`).
* **LLM synthesis** — `google-genai` 1.30 (`gemini-1.5-flash` default) with legacy `google-generativeai` fallback, dynamic model discovery, tenacity retries, and structured JSON report schema.
* **PDF / SEC ingestion** — `POST /api/ingest/pdf` (multipart, ≤10 MB, PyMuPDF text + tables, optional vision) and `POST /api/ingest/sec?days_back=3` (Finnhub 8-K for NVDA/TSM/INTC/AMD/AAPL/ASML/…).
* **Live feed** — SWR polling (5s, pause when WebSocket open) plus `WebSocket /api/ws/signals?token=JWT` (10s push on hash change, ping/pong, exponential reconnect, 4401 on auth failure).
* **Manual injection** — `POST /api/inject` with fingerprint dedup and optional Supabase audit.
* **Source verification & export** — Trust levels (High/Medium/Low) and export to `md`/`json`/`txt`.
* **Observability** — `/health` (DB, stream, Gemini, vector), `/ping` (~1 ms, no I/O, for keep-alive), `/metrics` (uptime, request/error counts, dedup count, vector count, embedding cache).

---

## Architecture

```mermaid
graph TD
    subgraph Sources
        NewsAPI[NewsAPI]
        GDELT[GDELT]
        HN[HackerNews Algolia]
        Finnhub[Finnhub 8K]
        PDF[PDF Upload]
        Manual[Manual Inject]
    end

    Sources -->|append JSONL| Stream[data/stream.jsonl]
    Stream --> Pathway{Pathway Pipeline<br/>Linux/WSL}
    Pathway -->|normalize + dedup| POut[data/pathway_out.jsonl]
    Stream -->|fallback| Scheduler[APScheduler 5m]
    Scheduler -->|pull| NewsAPI & GDELT & HN

    subgraph Backend[FastAPI]
        API[/api/*]
        Auth[Clerk JWT<br/>RS256 JWKS]
        Limiter[slowapi]
        Vector[(Vector Store<br/>pgvector → Chroma)]
        Graph[[Graph Store<br/>19 edges BFS]]
        LLM[Gemini Client]
        WS{{WS /api/ws/signals}}
        Health[/health /ping /metrics]
    end

    API --> Auth & Limiter
    API --> Vector & Graph & LLM & Health & WS
    PDF -->|extract text/tables| LLM
    Finnhub --> LLM

    subgraph Frontend[React + Vite]
        Home[Home /]
        SignIn[/sign-in /sign-up]
        Dash[Dashboard]
        SWR[SWR 5s] --> API
        WS --> API
    end

    Dash -->|query / generate| API
    Dash -->|graph / simulate| Graph
    Dash -->|PDF modal| PDF
```

**Data paths** (configurable via env): `DATA_STREAM_PATH` (default `data/stream.jsonl`), `DB_PATH` (`data/siliconpulse.db`), `PATHWAY_OUTPUT_PATH` (`data/pathway_out.jsonl`), Chroma at `data/chroma`.

---

## Tech Stack

| Layer | Components |
|-------|------------|
| **Frontend** | React 19.2, React Router 7.13, Vite 6.2, Tailwind, lucide-react, react-markdown 10, SWR 2.5, Clerk `@clerk/clerk-react` 5.61, Playwright 1.62, nginx (prod), chunk-split `vendor`/`clerk`/`genai`/`swr` |
| **Backend** | FastAPI 0.115, Uvicorn 0.32, Pydantic 2.9, pydantic-settings 2.5, APScheduler 3.10, slowapi 0.1.9, PyJWT 2.10, Supabase 2.15, httpx 0.28, requests 2.32, tenacity 8.5 |
| **AI** | `google-genai` 1.30 + `google-generativeai` 0.8 fallback, `gemini-embedding-001` 768-dim (SHA-256 cache, 5k entries), PyMuPDF 1.23 for PDF |
| **Storage** | JSONL stream, SQLite dedup (`seen_events`), Chroma 1.5 `data/chroma` (cosine) or Supabase `pgvector` (`signals_vec` 768 + `match_signals` RPC + `ivfflat`) |
| **Infra** | Docker multi-stage (`python:3.11-slim` → `node:20-alpine` → `nginx:alpine`), docker-compose with `service_healthy`, GitHub Actions CI |

---

## Prerequisites

* Python **3.11**
* Node.js **20**
* A Clerk project (for `CLERK_ISSUER`, `CLERK_AUDIENCE`, `VITE_CLERK_PUBLISHABLE_KEY`) — see <https://dashboard.clerk.com>
* Google Gemini API key — <https://aistudio.google.com/apikey>
* Supabase project (optional but recommended for pgvector + audit) — <https://supabase.com>
* Optional: NewsAPI key, Finnhub key (for SEC filings)

---

## Installation

```bash
git clone https://github.com/SanskarG-20/SiliconPulse.git
cd SiliconPulse
cp .env.example .env   # then edit required keys
```

**Backend:**

```bash
cd backend
python -m venv venv
# Windows
.\venv\Scripts\Activate.ps1
# Linux / macOS
source venv/bin/activate
pip install -r requirements.txt
```

**Frontend:**

```bash
cd frontend
npm ci
```

---

## Environment Configuration

All settings are loaded by `backend/app/settings.py` (Pydantic Settings, `env_file=.env`, `extra=ignore`). Frontend reads `VITE_*` via Vite `loadEnv`.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `GEMINI_API_KEY` | Yes | — | Google AI Studio key for generation + embeddings |
| `CLERK_ISSUER` | Yes | — | e.g. `https://<instance>.clerk.accounts.dev` |
| `CLERK_AUDIENCE` | Yes | — | Clerk audience / instance identifier |
| `VITE_CLERK_PUBLISHABLE_KEY` | Yes (frontend) | — | `pk_test_...` / `pk_live_...` |
| `SUPABASE_URL` | Recommended | — | `https://<project>.supabase.co` |
| `SUPABASE_SERVICE_ROLE_KEY` | Recommended | — | Service role key (server-side only) |
| `NEWSAPI_API_KEY` | No | — | NewsAPI.org key |
| `FINNHUB_API_KEY` | No | — | Finnhub key for SEC 8-K |
| `VITE_API_BASE_URL` | No | `http://127.0.0.1:8000/api` | Backend base for frontend |
| `HOST` / `PORT` | No | `0.0.0.0` / `8000` | Uvicorn bind |
| `DATA_STREAM_PATH` | No | `data/stream.jsonl` | JSONL stream relative to `backend/` |
| `DB_PATH` | No | `data/siliconpulse.db` | SQLite dedup DB |
| `PATHWAY_OUTPUT_PATH` | No | `data/pathway_out.jsonl` | Pathway output |
| `USE_PATHWAY` | No | `platform != Windows` | Force `True`/`False` |
| `FRESHNESS_HOURS` | No | `12` | `safe_read_jsonl` filter window |
| `MAX_EVENTS_TO_SCAN` | No | `500` | Max events scanned per query |
| `GDELT_ENABLED` / `HACKERNEWS_ENABLED` | No | `True` | Toggle free sources |
| `GEMINI_MODEL` | No | `gemini-1.5-flash` | Primary generation model |

> Never commit `.env`. `SUPABASE_SERVICE_ROLE_KEY` and `GEMINI_API_KEY` are server-only. `VITE_*` keys are bundled into the client.

---

## Running Locally

### Windows (Polling Mode)

Pathway does not run natively on Windows. Keep `USE_PATHWAY=False` (auto-detected) and use the APScheduler fallback.

```bash
# Terminal 1 — API + scheduler (includes first background pull)
cd backend
.\run_backend.ps1
# equivalent: uvicorn app.main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
# Vite serves at http://localhost:3000 (Playwright uses 5173 via --port flag)
```

### Linux / WSL2 / macOS (Full Streaming)

```bash
# Terminal 1 — Pathway pipeline (true streaming)
cd backend
python pathway_pipeline.py   # if present; otherwise skip and use scheduler

# Terminal 2 — API
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 3 — Frontend
cd frontend
npm run dev
```

Open `http://localhost:3000` (or `http://localhost:5173` when started via Playwright). Health checks:

```bash
curl http://localhost:8000/health | jq
curl http://localhost:8000/ping
curl http://localhost:8000/metrics | jq
curl http://localhost:8000/api/graph/explain/TSMC -H "Authorization: Bearer <clerk_jwt>" | jq
```

### Docker Compose (Production-like)

```bash
cp .env.example .env  # fill required keys
docker compose up --build
# Frontend http://localhost:3000 (nginx proxies /api → backend:8000)
# Backend  http://localhost:8000 (and /docs)
```

Volumes persist `./backend/data`. Healthcheck: `curl -f http://localhost:8000/health` every 30s.

---

## API Documentation

All `/api/*` routes (except WebSocket upgrade) require `Authorization: Bearer <Clerk_JWT>` validated via `backend/app/core/auth.py` (RS256 JWKS from `CLERK_ISSUER/.well-known/jwks.json`). Rate limiting via `slowapi` (`memory://`), default `100/minute` plus per-route limits.

Base URL locally `http://localhost:8000`; in prod via `VITE_API_BASE_URL`.

| Method | Path | Auth | Rate | Description |
|--------|------|------|------|-------------|
| `GET` | `/` | No | — | Service banner |
| `GET` | `/health` | No | — | DB, stream file, `gemini_configured`, vector count, `uptime_seconds` |
| `GET` | `/ping` | No | — | ~1 ms liveness, no I/O (for UptimeRobot) |
| `GET` | `/metrics` | No | — | `uptime_seconds`, `requests_total`, `errors_total`, `stream_file_bytes`, `dedup_seen_events`, `vector_signals`, `embedding_cache_entries` |
| `GET` | `/api/signals` | Clerk | — | Latest 20 signals (freshness-filtered) |
| `POST` | `/api/inject` | Clerk | `10/min` | `InjectRequest {title, content, source, timestamp?}` → dedup via `compute_event_id` SHA-256 |
| `POST` | `/api/query` | Clerk | `30/min` | `QueryRequest {query, k}` → hybrid retrieval + `signal_strength`/`confidence` |
| `POST` | `/api/generate` | Clerk | `10/min` | `GenerateRequest {query, context}` + Graph RAG enrichment → Gemini JSON report |
| `GET` | `/api/radar` | Clerk | — | Per-company activity (High ≥5, Moderate ≥2) |
| `GET` | `/api/sources/*` | Clerk | — | Trust/verify helpers |
| `POST` | `/api/export` | Clerk | — | `ExportRequest {query, report, evidence, format=md|json|txt, include_evidence}` |
| `GET` | `/api/llm/health` | Clerk | — | Gemini key + model probe |
| `GET` | `/api/llm/models` | Clerk | — | Discovered Gemini models |
| `POST` | `/api/ingest/pdf` | Clerk | `10/min` | Multipart `file` (PDF, ≤10 MB) → PyMuPDF text/tables → `extract_events_from_text` → dedup + vector |
| `POST` | `/api/ingest/sec?days_back=3` | Clerk | `5/min` | Finnhub 8-K for NVDA/TSM/INTC/AMD/… → LLM (3 events each) → dedup |
| `GET` | `/api/graph/nodes` | Clerk | — | Sorted company nodes |
| `GET` | `/api/graph/edges` | Clerk | — | List of `Edge {source, target, relation, weight}` |
| `GET` | `/api/graph/impact/{company}?depth=2` | Clerk | — | Downstream BFS score = product(weights) |
| `GET` | `/api/graph/suppliers/{company}?depth=2` | Clerk | — | Reverse BFS upstream |
| `GET` | `/api/graph/explain/{company}?depth=2` | Clerk | — | Human-readable supply-chain context |
| `POST` | `/api/graph/simulate` | Clerk | `15/min` | `{company, shock: -0.9..0.9, depth, metric}` → `shocked_score = original*(1+shock)`, `$M` est, LLM scenario |
| `WS` | `/api/ws/signals?token=JWT` | Query JWT | — | Push on content hash change every 10s, `ping`→`pong`, close `4401` if auth fails |

Interactive docs when running: `http://localhost:8000/docs` (OpenAPI) and `/redoc`.

---

## Project Structure

```
SiliconPulse/
├── backend/
│   ├── app/
│   │   ├── main.py                 # FastAPI app, lifespan, /health /ping /metrics, CORS, global handler
│   │   ├── settings.py             # Pydantic Settings (env)
│   │   ├── storage.py              # SQLite seen_events + checkpoints
│   │   ├── scheduler.py            # APScheduler 5m news + 6h SEC, fallback thread on Windows
│   │   ├── ws.py                   # WebSocket /ws/signals (JWT via ?token=)
│   │   ├── utils.py                # extract_companies, classify, SHA-256 dedup, safe_read_jsonl, confidence
│   │   ├── company_dict.py         # Canonical companies + aliases
│   │   ├── query_cache.py          # LRU 60s query cache
│   │   ├── core/auth.py            # Clerk RS256 JWKS verification
│   │   ├── core/limiter.py         # slowapi Limiter
│   │   ├── graph/store.py          # 19-edge DAG, BFS, simulate_scenario
│   │   ├── graph/routes.py         # /graph/* endpoints
│   │   ├── routes/
│   │   │   ├── signals.py          # GET /signals, POST /inject
│   │   │   ├── query.py            # POST /query, GET /radar, POST /generate
│   │   │   ├── ingest.py           # POST /ingest/pdf, /ingest/sec
│   │   │   ├── llm.py              # GET /llm/health, /llm/models
│   │   │   └── ...                 # sources, export, recommendations, diagnostics
│   │   └── services/
│   │       ├── gemini_client.py    # google-genai + legacy fallback, model discovery, retries
│   │       ├── embedding_service.py# gemini-embedding-001, 5k SHA-256 cache
│   │       ├── vector_store.py     # facade: pgvector → Chroma
│   │       ├── pgvector_store.py   # Supabase signals_vec + match_signals RPC
│   │       ├── pdf_parser.py       # PyMuPDF text/tables/images + vision
│   │       ├── ingestion_pipeline.py # PDF/SEC → LLM events → dedup+vector
│   │       ├── llm_extractor.py    # prompt → strict JSON events
│   │       └── news_sources.py     # GDELT/HN/NewsAPI aggregator
│   ├── tests/                      # pytest: smoke, query_flow, graph, vector, ws, sec_filings
│   ├── data/                       # stream.jsonl, siliconpulse.db, chroma/ (gitignored)
│   ├── requirements.txt
│   ├── Dockerfile                  # python:3.11-slim, healthcheck
│   └── run_backend.ps1
├── frontend/
│   ├── App.tsx                     # Home + /sign-in /sign-up /dashboard + SignedIn/SignedOut
│   ├── index.tsx                   # ClerkProvider guard (missing key → Deployment Configuration Error)
│   ├── vite.config.ts              # port 3000, alias @, manualChunks
│   ├── nginx.conf                  # / → index.html, /api/ → backend:8000
│   ├── components/dashboard/       # Dashboard, QueryZone, Header, Sidebar, etc.
│   ├── hooks/                      # useDashboard, useSignalsWS
│   ├── e2e/                        # Playwright health + query-flow specs
│   ├── Dockerfile                  # node:20-alpine build → nginx:alpine
│   └── package.json
├── .github/workflows/ci.yml        # Backend + Frontend + E2E jobs
├── docker-compose.yml
├── .env.example
└── README.md
```

---

## Data & Ingestion Flow

**Stream file** `data/stream.jsonl` — one JSON object per line: `{title, content, timestamp, source, company?, event_type?, url?}`. Read via `safe_read_jsonl(limit, freshness_hours)`; fresh by default 12h.

**Dedup** — `compute_event_id` normalizes `title|url|source` (or `title|content[:200]|source`) → SHA-256. `storage.is_duplicate` / `mark_seen` in SQLite; `deduplicate_and_append` writes only new events and fires best-effort vector upsert (async task or background thread).

**Sources polled by `scheduler.pull_all_sources` every 5 min:**
* Unified news (`services/news_sources.ingest_news_stream_sync`)
* GDELT (`sources/gdelt_source.pull_gdelt_signals`)
* HackerNews Algolia (`sources/hackernews_source.pull_hn_signals`)
* SEC 8-K every 6h (`pull_sec_filings_sync` → `ingest_sec_filings(days_back=3)`)

**PDF path:** `POST /api/ingest/pdf` validates `.pdf` ≤10 MB → `pdf_parser.extract_text` + `extract_tables` (markdown rows) → `ingestion_pipeline.ingest_pdf_bytes` → `llm_extractor.extract_events_from_text` (max 10 events, focused on earnings/guidance/capex/yield) → `deduplicate_and_append`.

**SEC path:** `POST /api/ingest/sec` → `sec_filings.SECFilingsService` (Finnhub) → per-filing `extract_events_from_text` (max 3) → tag with `url`/`timestamp` → `deduplicate_and_append`.

---

## Vector & LLM Flow

**Embeddings** — `embedding_service.embed_texts` with SHA-256 memoization (5k cap, evict half on overflow). `EMBED_MODEL=gemini-embedding-001`, `EMBED_DIM=768`, 15s timeout, no-op (returns `None`) when `GEMINI_API_KEY` missing.

**Vector store facade** — `vector_store.is_available()` checks `pgvector_store.is_available()` (Supabase `signals_vec` table probe) then Chroma `PersistentClient(data/chroma)`. `upsert_signals` and `query_similar` try pgvector first, fall back to Chroma. Chroma distance → similarity `1 - distance`; pgvector returns `similarity`/`distance` from `match_signals` RPC.

**Query** (`routes/query.py:process_query`):
1. LRU `query_cache` hit?
2. `safe_read_jsonl(max_events_to_scan=500, freshness_hours=12)`
3. Vector search (top 30) → `vector_hits: title→similarity`
4. Keyword expansion via `COMPANY_DICT` aliases (longest-first) + original keywords
5. Keyword match over title/content/company
6. Merge vector-only hits where `similarity ≥ 0.72`
7. Dedup by `(title, source)`, sort by timestamp, slice `k` (1–20), `compute_confidence`
8. Persist to `query_cache` and Supabase audit.

**Generation** (`POST /api/generate`): extracts companies from query → `graph.store.get_impact`/`get_suppliers` context → prompt with `GRAPH CONTEXT` + evidence block → `gemini_client.generate_content_with_fallback` (discovered model list, 2 retries, 10s timeout). Falls back to simulation JSON when key missing or zero evidence. Response is a JSON string with sections `evidence`, `change`, `impact`, `competitors`, `outlook`, `confidence`, `ceo`.

**Graph** — `graph/store.py:EDGES` static, `_ADJ` forward and reverse, BFS product-weight scoring, `simulate_scenario` with `factor = max(0.05, 1+shock)`, `est_impact_usd_m = int(abs(delta)*10000)`, severity High >0.15 else Medium >0.07 else Low.

---

## Testing

```bash
# Backend — pytest (requires PYTHONPATH=.)
cd backend
$env:PYTHONPATH="."           # PowerShell
# export PYTHONPATH="."       # bash
pytest tests/ -v              # all suites
pytest tests/ -v -k "smoke or query or graph"

# Frontend — typecheck + lint + build
cd frontend
npm run build                 # vite build (tsc + bundler, respects chunk limits)
npx tsc --noEmit              # typecheck only
npx eslint .                  # lint (ci runs with || true)
npm run test                  # Vitest (jsdom) — GraphPanel + GraphExplorer

# E2E — Playwright (needs both servers or uses webServer)
cd frontend
npm run e2e                   # playwright test
npx playwright test --reporter=list
# CI spawns: npm run dev -- --port 5173 --host 127.0.0.1  +  python -m uvicorn app.main:app --port 8000
```

Tests cover: `test_smoke.py`, `test_query_flow.py`, `test_graph.py`, `test_vector.py`, `test_vector_fallback.py`, `test_ingest.py`, `test_ws.py`, `test_sec_filings.py` (see `backend/tests/`). Frontend: `GraphPanel.test.tsx` + `GraphExplorer.test.tsx` (Vitest + Testing Library, jsdom). E2E specs: `e2e/health.spec.ts` and `e2e/query-flow.spec.ts`.

---

## CI/CD

Workflow `.github/workflows/ci.yml` triggers on `push`/`pull_request` to `main`/`develop`:

| Job | Runner | Steps |
|-----|--------|-------|
| **Backend Tests & Lint** | `ubuntu-latest`, Python 3.11, `pip` cache | `pip install -r requirements.txt` → `ruff check app/ tests/ \| true` → `mypy app/ --ignore-missing-imports \| true` → `PYTHONPATH=. pytest tests/ -v` |
| **Frontend Build & Lint** | `ubuntu-latest`, Node 20, `npm` cache | `npm ci` → `npx eslint . \| true` → `npx tsc --noEmit` → `npm run test` (Vitest) → `npm run build` |
| **E2E Playwright** | `ubuntu-latest`, needs backend+frontend | `pip install` + `npm ci` + `npx playwright install --with-deps chromium` → `npx playwright test --reporter=list` with `PYTHONPATH=../backend`, `CI=true`, `VITE_CLERK_PUBLISHABLE_KEY=<dummy>` and `webServer` on 5173/8000 |

Lint steps are non-blocking (`|| true`); typecheck and tests are blocking.

---

## Deployment

**Docker Compose** — `docker-compose.yml` builds `backend` (`python:3.11-slim`, `curl` healthcheck), `redis:7-alpine` (for `REDIS_URL=redis://redis:6379/0` distributed limiter) and `frontend` (`node:20-alpine` build → `nginx:alpine`). Frontend `nginx.conf` proxies `/api/` and `/health` to `backend:8000`. Data persists at `./backend/data:/app/data` + `redis_data`. Run `docker compose up --build`; frontend on `3000`, backend on `8000`, redis on `6379`.

**Render (backend) + Vercel (frontend)** recommended:

* **Backend on Render:** set `HOST=0.0.0.0`, `PORT=8000`, all env from `.env.example`. Healthcheck `GET /health`. Free tier sleeps after 15 min — prevent with an UptimeRobot cron hitting `GET /ping` every 5 min (use `/ping`, not `/health`, to avoid DB/vector work). Alternatives: cron-job.org or paid Render.
* **Frontend on Vercel:** set `VITE_API_BASE_URL=https://<render-backend>/api` and `VITE_CLERK_PUBLISHABLE_KEY`. The app shows `Deployment Configuration Error` at `/` if `VITE_CLERK_PUBLISHABLE_KEY` is missing. Redeploy after changing env.

**Common deploy env:** `GEMINI_API_KEY`, `CLERK_ISSUER`, `CLERK_AUDIENCE`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optional `NEWSAPI_API_KEY`/`FINNHUB_API_KEY`.

---

## Security Considerations

* **Auth** — Every `/api/*` (and WS via `?token=`) validates a Clerk-issued RS256 JWT against `CLERK_ISSUER/.well-known/jwks.json`. Missing/invalid token → `401`. `audience` verified only when `CLERK_AUDIENCE` is set.
* **CORS** — `allow_origins=["*"]`, `allow_credentials=False`, `allow_headers=["*"]` to support Vercel preview URLs. Do not switch `allow_credentials` to `True` without restricting origins, or browsers will block `Authorization` headers.
* **Rate limiting** — `slowapi` with `memory://` by default, `REDIS_URL=redis://redis:6379/0` for distributed (see `backend/app/core/limiter.py:8` and `docker-compose.yml:redis`); per-route limits above. Global exception handler falls back to 200 with empty evidence for `/query` on unhandled errors to avoid UI hangs; other paths return 500.
* **Row Level Security** — Supabase `supabase/migrations/001_rls.sql` enables RLS on `users`/`queries`/`insights`/`signals` (`user_id = auth.uid()::text`) and read-only `signals_vec` for `authenticated`; `service_role` bypasses RLS for server writes. Apply via Supabase SQL Editor; `get_user_scoped_client(jwt)` in `supabase_client.py:58` shows per-user flow.
* **Secrets** — `.env` is gitignored (`extra=ignore` in settings). Never expose `SUPABASE_SERVICE_ROLE_KEY` or `GEMINI_API_KEY` to the client; only `VITE_*` vars are bundled. Rotate keys via dashboard and redeploy.
* **Validation** — Pydantic models (`QueryRequest` 1–500 chars, `k` 1–20; `InjectRequest` title 1–200, content 1–5000; `ExportRequest` format `md|json|txt`) and PDF size/type checks.

---

## Troubleshooting

| Symptom | Likely cause | Fix |
|---------|--------------|-----|
| `No text extracted from PDF` | Scanned PDF without OCR text layer | Enable `use_vision=True` (Gemini vision) or provide text-based PDF |
| `CLERK_ISSUER is not configured` (401) | `CLERK_ISSUER` missing on backend | Set `CLERK_ISSUER=https://<instance>.clerk.accounts.dev` and restart |
| Frontend `Deployment Configuration Error` | `VITE_CLERK_PUBLISHABLE_KEY` not set at build | Add it in Vercel → Settings → Environment Variables → Redeploy |
| `Backend offline (tried http://localhost:8000/api)` in prod | `VITE_API_BASE_URL` still `localhost` | Set `VITE_API_BASE_URL=https://<backend>.onrender.com/api` in Vercel |
| `Backend is waking up (30-50s)` | Render free tier cold start | Wait, or add UptimeRobot hitting `/ping` every 5 min |
| Pathway errors on Windows | `pathway` wheel unavailable on Windows | Keep `USE_PATHWAY=False`; scheduler fallback handles ingestion |
| Vector search disabled | No Gemini key or Chroma/pgvector unavailable | Check `GET /health` → `vector_store` and `gemini_configured`; ensure `GEMINI_API_KEY` set and `data/chroma` writable |
| Port conflict `5173` vs `3000` | Playwright uses `5173 --port` override while `vite.config.ts` defaults to `3000` | Both are valid; `npm run dev` alone uses `3000`, CI E2E overrides to `5173` |
| `psycopg`/`supabase` table missing | `signals_vec` not created | Run the SQL from `supabase` dashboard to create `signals_vec` + `match_signals` + `ivfflat` index |

---

## Roadmap

- [x] Graph RAG (19-edge DAG, BFS impact/suppliers, LLM enrichment)
- [x] Vector search (768-dim, Chroma + pgvector, hybrid ≥0.72)
- [x] Keep-alive `/ping` + UptimeRobot guidance
- [x] WebSocket live feed (`/api/ws/signals` + SWR fallback)
- [x] PDF / SEC ingestion (PyMuPDF + Finnhub + LLM extraction)
- [x] Scenario engine (`/api/graph/simulate` + LLM report)
- [x] D3 force-graph explorer (`GraphExplorer.tsx` — force simulation, zoom/pan, drag, 19-node DAG, collapsible in Dashboard + sidebar `GraphPanel` detail)
- [x] Supabase Row-Level Security (`supabase/migrations/001_rls.sql` + `supabase_client.py:58` per-user client, `signals_vec` read-only for authenticated)
- [x] Frontend tests for GraphPanel / Scenario slider (`GraphPanel.test.tsx` + `GraphExplorer.test.tsx`, Vitest + jsdom, 6 tests)
- [x] Ingest & vector fallback coverage (`test_ingest.py` + `test_vector_fallback.py`, 12 tests, 44 total backend)
- [x] Distributed limiter via Redis (`limiter.py:8` `REDIS_URL`, `docker-compose.yml:redis`)
- [x] Distributed ingestion workers (`app/workers/distributed.py` shard-aware pool, `app/workers/queue.py` Redis Stream → memory fallback, `app/workers/pathway_distributed.py` sharded Pathway, `docker-compose.yml:worker` + `WORKER_COUNT`)

---

## Contributing

1. Fork and branch from `main`.
2. `cp .env.example .env` and fill required keys; do not commit `.env`.
3. Follow existing style: `ruff` for Python, `eslint` + `tsc` for frontend. CI runs `ruff | true` and `eslint | true` but please fix warnings locally.
4. Add/adjust tests in `backend/tests/` and `frontend/e2e/` for new behavior.
5. Open a PR against `develop` (or `main` if hotfix); ensure `PYTHONPATH=. pytest` and `npm run build` pass.

---

## License

MIT — see `LICENSE` if present. If no `LICENSE` file is committed, all rights are reserved to the repository owner.

---

<div align="center">

Built with FastAPI, Pathway, Gemini, and React.

</div>
