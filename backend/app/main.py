import logging
import time
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .core.auth import get_current_user
from .core.limiter import limiter
from .routes import router
from .supabase_client import is_supabase_enabled
from .settings import settings
from .storage import get_db_connection, init_db
from .utils import now_ts

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

START_TIME = time.time()
REQUEST_COUNT = 0
ERROR_COUNT = 0


@asynccontextmanager
async def lifespan(app: FastAPI):
    # startup
    logger.info("Starting up SiliconPulse API...")
    if is_supabase_enabled():
        from .services.signal_store import check_ready

        check_ready()
        logger.info("Supabase/Postgres canonical storage verified")
    else:
        if settings.app_env.lower() == "production":
            raise RuntimeError("APP_ENV=production requires Supabase/Postgres configuration")
        init_db()
        logger.info("Initialized local-development storage at %s", settings.db_path)
    yield
    # shutdown
    logger.info("Shutting down SiliconPulse API...")


app = FastAPI(
    title=settings.app_name,
    description="Strategic Intelligence Backend",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware — allow all origins (Vercel preview URLs are dynamic)
# Must have allow_credentials=False when using "*" per CORS spec, otherwise browser blocks Authorization header
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)

# Metrics middleware
@app.middleware("http")
async def metrics_middleware(request: Request, call_next):
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    response = await call_next(request)
    global ERROR_COUNT
    if response.status_code >= 500:
        ERROR_COUNT += 1
    return response


# Global Exception Handler
# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    global ERROR_COUNT
    ERROR_COUNT += 1
    logger.error(f"Global exception: {str(exc)}", exc_info=True)

    # If it's the query endpoint, return a safe fallback
    if request.url.path.endswith("/query"):
        return JSONResponse(
            status_code=200,
            content={
                "query": "Error processing query",
                "evidence": [],
                "signal_strength": 0,
                "last_updated": now_ts(),
                "report": None,
                "llm_status": "failed"
            }
        )

    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal Server Error",
            "error": str(exc),
            "path": request.url.path,
            "timestamp": now_ts()
        }
    )

# Include API routes with /api prefix
app.include_router(router, prefix="/api", tags=["api"])

# WebSocket routes (mounted at /api, so endpoint = /api/ws/signals)
from .ws import router as ws_router  # noqa: E402

app.include_router(ws_router, prefix="/api", tags=["ws"])


@app.get("/")
async def root():
    return {"message": "SiliconPulse backend running"}


@app.get("/health")
async def health():
    # Detailed health checks
    checks = {}
    # Canonical store check, or local-development SQLite check.
    try:
        if is_supabase_enabled():
            from .services.signal_store import check_ready

            check_ready()
        else:
            conn = get_db_connection()
            conn.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    checks["signal_store"] = "Supabase/Postgres" if is_supabase_enabled() else "local-development JSONL cache"
    # Gemini check
    checks["gemini_configured"] = bool(settings.gemini_api_key)
    # Vector store check
    try:
        from .services.vector_store import count as vector_count
        from .services.vector_store import is_available
        if is_available():
            checks["vector_store"] = f"ok ({vector_count()} vectors)"
        else:
            checks["vector_store"] = "unavailable (semantic search disabled)"
    except Exception as e:
        checks["vector_store"] = f"error: {e}"
    # Overall
    overall = "online" if checks["database"] == "ok" else "degraded"
    return {"status": overall, "service": "siliconpulse-backend", "checks": checks, "uptime_seconds": int(time.time() - START_TIME)}


@app.get("/ping")
async def ping():
    """
    Ultra-light keep-alive endpoint for UptimeRobot / external cron.
    No DB / file / vector checks — just proves the process is alive.
    Pinging this every <15min prevents Render free tier spin-down.
    """
    return {"ok": True, "t": int(time.time())}


@app.get("/metrics", dependencies=[Depends(get_current_user)])
async def metrics():
    uptime = int(time.time() - START_TIME)
    # Stream stats
    stream_path = settings.resolved_data_path
    from .services.signal_store import is_enabled as canonical_store_enabled
    stream_size = stream_path.stat().st_size if (not canonical_store_enabled() or settings.local_cache_enabled) and stream_path.exists() else 0
    # DB stats
    try:
        from .storage import seen_count as get_seen_count

        seen_count = get_seen_count()
    except Exception:
        seen_count = -1
    # Vector stats
    try:
        from .services.embedding_service import cache_size as embed_cache_size
        from .services.vector_store import count as vector_count
        from .services.vector_store import is_available
        vector_count_val = vector_count() if is_available() else -1
        embed_cache = embed_cache_size()
    except Exception:
        vector_count_val = -1
        embed_cache = -1
    # Worker stats (distributed)
    try:
        from app.workers.distributed import get_pool

        wp = get_pool()
        w_stats = wp.stats()
        w_depth = wp.depth()
    except Exception:
        w_stats = {"processed": 0, "batches": 0, "errors": 0, "workers": 0}
        w_depth = {"backend": "memory", "shards": 0}
    return {
        "uptime_seconds": uptime,
        "requests_total": REQUEST_COUNT,
        "errors_total": ERROR_COUNT,
        "stream_file_bytes": stream_size,
        "dedup_seen_events": seen_count,
        "vector_signals": vector_count_val,
        "embedding_cache_entries": embed_cache,
        "workers": w_stats,
        "queue": w_depth,
        "timestamp": now_ts(),
    }
