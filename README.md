<div align="center">
  <h1>⚡ SiliconPulse</h1>
  <p><b>Real-time Strategic Intelligence for the Semiconductor & AI Ecosystem</b></p>

  [![Status](https://img.shields.io/badge/Status-Active-success)](#)
  [![Tech](https://img.shields.io/badge/Stack-FastAPI%20%7C%20React%20%7C%20Gemini%20%7C%20Pathway-blue)](#)
  [![License](https://img.shields.io/badge/License-MIT-green)](#)

</div>

---

## 📖 Overview

**SiliconPulse** is an advanced, real-time strategic intelligence engine designed to decode the rapidly evolving semiconductor, AI, and tech startup markets. It autonomously aggregates live signals—from global news, market data, and tech journals—grounds them in verified evidence, and leverages **Google Gemini** to synthesize executive-level strategic insights instantly.

Unlike static dashboards, SiliconPulse is **reactive and intent-aware**. It understands the strategic implications of supply chain disruptions, AI model launches, or sudden funding rounds, and explains *why* it matters, backed by a dynamic confidence assessment and real-time Entity Recognition.

---

## ✨ Key Features

- 📡 **Live Pulse Feed & Ingestion**: A real-time data pipeline that ingests, normalizes, and deduplicates signals on the fly with a 12-hour freshness window.
- 🧠 **Strategic Insight Engine (RAG)**: Powered by Gemini (google-genai 1.30), generating structured reports outlining Immediate Shifts, Impact Reasoning, Competitor Effects, and Strategic Outlooks.
- 🎯 **Universal Company Radar**: Dynamically extracts organizations using robust regex/NLP heuristics to track the pulse of every startup, tech giant, and entity mentioned in the stream—unbound by static dictionaries.
- 💉 **Live Signal Injection**: Manually inject custom intelligence into the live stream and watch the AI instantly adapt its analysis and confidence scoring.
- ✅ **Source Verification & End-to-End Export**: Automated trust-scoring for sources (High/Medium/Low) with justification. Export full intelligence briefings to Markdown, JSON, or Text.
- 🎬 **Cinematic Command Center UI**: High-fidelity React interface featuring atmospheric styling and real-time interactive components.
- 🕸️ **Graph RAG (Supply-Chain)**: In-memory knowledge graph (ASML→TSMC→NVIDIA→Microsoft) with BFS impact/supplier scoring, wired into LLM prompt for deeper reasoning.
- 📊 **Observability**: Detailed `/health` + `/metrics` (uptime, request/error counts, stream size, dedup), rate-limiting (slowapi), structured logging.
- ⚡ **SWR Polling**: Frontend uses `swr` stale-while-revalidate (5s poll, 4s dedup) instead of raw `setInterval`.

---

## 🏗️ Architecture

SiliconPulse relies on a highly decoupled architecture designed for streaming data velocity, utilizing **Pathway** for real-time processing and **FastAPI** as the intelligence gateway.

```mermaid
graph TD
    subgraph "Ingestion & Streaming Layer"
        Sources[News APIs / GDELT / Manual] -->|Append| RawStream[data/stream.jsonl]
        RawStream -->|Read| Pathway[Pathway Pipeline]
        Pathway -->|Normalize + Dedup + Extract Entities| ProcessedStream[data/pathway_out.jsonl]
    end

    subgraph "Backend (FastAPI)"
        API[API Gateway] --> QueryEngine
        API --> RadarService
        API --> Graph[Graph RAG Store]
        API --> Metrics[/health + /metrics]
        QueryEngine -->|Retrieve| ProcessedStream
        QueryEngine -->|Enrich| Graph
        QueryEngine -->|Synthesize| LLM[Google Gemini 2.0/2.5]
    end

    subgraph "Frontend (React + Vite)"
        UI[Dashboard] -->|SWR Poll 5s| API
        UI -->|Query Insights| QueryEngine
        UI -->|GraphPanel| Graph
    end
```

### The Streaming Pipeline (Pathway)
- **Normalization**: Cleanses unstructured text for downstream RAG.
- **Deduplication**: Computes stable SHA-256 fingerprints for events to ensure distinct processing.
- **Universal Entity Extraction**: Employs real-time heuristics to auto-tag organizations across the tech spectrum.

### Graph RAG Store
- 19 static edges (ASML→TSMC→NVIDIA→Microsoft, etc.) with weights
- BFS `get_impact` / `get_suppliers` up to depth 3, score = product of weights
- Endpoints: `/api/graph/nodes`, `/edges`, `/impact/{co}`, `/suppliers/{co}`, `/explain/{co}` — wired into `/generate` prompt as “GRAPH CONTEXT”.

---

## 🚀 Getting Started

### Prerequisites
- **Python 3.11+**
- **Node.js 18+**
- **Google Gemini API Key** (Get from [Google AI Studio](https://aistudio.google.com/apikey))
- **Clerk Account** for authentication (Get from [Clerk Dashboard](https://dashboard.clerk.com))
- **Supabase Project** for data persistence (Get from [Supabase](https://supabase.com))
- API Keys for News sources (NewsAPI.org) - *Optional but recommended for live streams.*

> ⚠️ **WINDOWS USERS - IMPORTANT LIMITATION**
> 
> **Pathway (the streaming engine) does NOT run natively on Windows.** It requires Linux, WSL2, or macOS.
> 
> **On Windows, the system works in "Polling Mode":**
> - The Pathway pipeline is disabled (`USE_PATHWAY=False` in `.env`)
> - A background scheduler pulls from NewsAPI, GDELT, and HackerNews every 5 minutes
> - Deduplication still works via SQLite checkpoints
> - For true streaming deduplication, run the backend in **WSL2** or deploy to Linux (Fly.io, Render, Railway)
> 
> See [`.env.example`](.env.example) for all configuration options.

### Installation & Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/SanskarG-20/SiliconPulse.git
   cd SiliconPulse
   ```

2. **Configure Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your API keys (required: GEMINI_API_KEY, CLERK_ISSUER, CLERK_AUDIENCE, SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
   ```

3. **Backend Setup**
   ```bash
   cd backend
   python -m venv venv
   # Windows:
   .\venv\Scripts\activate
   # Linux/Mac:
   source venv/bin/activate
   pip install -r requirements.txt
   ```

4. **Frontend Setup**
   ```bash
   cd frontend
   npm install
   ```

### Running the System

SiliconPulse requires **two services** on Windows (three on Linux/WSL) to run concurrently.

#### Windows (Default - Polling Mode)
```bash
# Terminal 1: API Server (includes background scheduler for data pulls)
cd backend
.\run_backend.ps1
# OR manually: uvicorn app.main:app --reload --port 8000

# Terminal 2: UI Dashboard (React)
cd frontend
npm run dev
```
Navigate to `http://localhost:5173` to access the Command Center.

#### Linux / WSL2 (Full Streaming Mode)
```bash
# Terminal 1: Data Pipeline (Pathway - true streaming)
cd backend
python pathway_pipeline.py

# Terminal 2: API Server (FastAPI)
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 3: UI Dashboard (React)
cd frontend
npm run dev
```

> **Note**: On Windows, set `USE_PATHWAY=False` in `.env` (default). The scheduler handles data ingestion every 5 minutes. On Linux/WSL, set `USE_PATHWAY=True` for real-time streaming.

### Docker (Production)

```bash
cp .env.example .env  # fill keys
docker compose up --build
# Frontend: http://localhost:3000  (nginx proxies /api → backend:8000)
# Backend:  http://localhost:8000  (health, metrics, docs at /docs)
```

- Multi-stage builds: `backend` (python:3.11-slim), `frontend` (node:20 → nginx:alpine)
- Volumes: `./backend/data` persisted for stream + SQLite

### API Highlights

- `POST /api/query` (30/min) — retrieve top-k evidence, signal_strength, confidence
- `POST /api/generate` (10/min) — Gemini report with Graph RAG enrichment
- `POST /api/inject` (10/min) — manual signal, dedup via SQLite
- `GET /api/graph/impact/{co}?depth=2` — downstream score BFS
- `GET /api/graph/explain/{co}` — LLM-ready context
- `GET /health` — detailed checks (DB, stream size, gemini)
- `GET /metrics` — uptime, requests_total, errors_total, dedup count

---

## 🧪 Testing & Verification

Run the automated tests (smoke + query-flow + graph + docker):

```bash
cd backend
export PYTHONPATH="."  # On Windows: $env:PYTHONPATH="."
pytest tests/ -v -k "smoke or query or graph"
# + frontend
cd ../frontend
npm run build        # vite + tsc check
npx eslint .         # lint
npm run e2e          # Playwright (needs backend + frontend running)
# or via compose:
docker compose up --build -d && curl http://localhost:8000/health && curl http://localhost:8000/metrics
```

Check backend health:
```bash
curl http://localhost:8000/health | jq
curl http://localhost:8000/metrics | jq
curl http://localhost:8000/api/graph/explain/TSMC | jq
```

### Keep-Alive (Render free tier)

Render free services spin down after 15 min idle → 30-50s cold start on next request. Prevent it with a free UptimeRobot monitor:

1. Sign up at [uptimerobot.com](https://uptimerobot.com) (free, 50 monitors / 5-min interval)
2. **Add New Monitor**:
   - Type: `HTTP(s)`
   - URL: `https://YOUR-BACKEND.onrender.com/ping`  *(ultra-light, no DB/vector checks)*
   - Interval: `5 minutes` (free tier minimum)
3. Save. Your backend now never sleeps.

> Alternative: [cron-job.org](https://cron-job.org) (free) hitting `/ping` every 10 min. Render paid plans ($7/mo) don't need this.

**Endpoints:** `/ping` (keep-alive, ~1ms) · `/health` (full checks: DB, stream, gemini, vector) · `/metrics` (uptime, requests, vector count)

---

## 🛠️ Tech Stack

- **Frontend**: React 19, Vite 6, Tailwind, Lucide, SWR (polling), Playwright (E2E), nginx (prod)
- **Backend**: FastAPI 0.115, Uvicorn, APScheduler, slowapi (rate-limit), lifespan, `re` heuristics
- **Data Processing**: Pathway (Linux) / Polling fallback (Windows)
- **AI / LLM**: Google Gemini 2.0/2.5 via `google-genai` 1.30 (fallback `google-generativeai`)
- **Storage**: JSONL (Streaming), SQLite (Metadata + dedup)
- **Graph**: In-memory supply-chain DAG (BFS scored)
- **Observability**: `/health` + `/metrics`, structured logging, Grafana-ready

---

## 🔮 Roadmap

- [x] **Graph RAG**: Map multi-tiered supply chain dependencies (ASML→TSMC→NVIDIA) — POC done (`/api/graph/*`, prompt enrichment)
- [ ] **Multi-Modal Ingestion**: Parse PDF earnings reports and financial charts automatically.
- [ ] **Distributed Streaming**: Scale to multiple Pathway workers to support 1M+ event ingestion per day.
- [ ] **Frontend Graph Viz**: D3 force-graph for live supply-chain explorer
- [ ] **PDF Vision**: `google-genai` vision for chart extraction

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---
<div align="center">
  Built with ❤️ using Google Gemini, Pathway & FastAPI.
</div>
