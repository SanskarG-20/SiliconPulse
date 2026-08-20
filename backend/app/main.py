import logging
import time
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from .core.limiter import limiter
from .routes import router
from .scheduler import start_scheduler, stop_scheduler
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
    logger.info(f"Using DATA_STREAM_PATH={settings.resolved_data_path}")
    init_db()
    logger.info("Database initialized")
    start_scheduler()
    logger.info("Real-time data scheduler started")
    yield
    # shutdown
    logger.info("Shutting down SiliconPulse API...")
    stop_scheduler()
    logger.info("Scheduler stopped")


app = FastAPI(
    title=settings.app_name,
    description="Strategic Intelligence Backend",
    version="1.0.0",
    lifespan=lifespan,
)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
@app.get("/")
async def root():
    return {"message": "SiliconPulse backend running"}


@app.get("/health")
async def health():
    # Detailed health checks
    checks = {}
    # DB check
    try:
        conn = get_db_connection()
        conn.execute("SELECT 1")
        checks["database"] = "ok"
    except Exception as e:
        checks["database"] = f"error: {e}"
    # Stream file check
    try:
        stream_path = settings.resolved_data_path
        if stream_path.exists():
            checks["stream_file"] = f"ok ({stream_path.stat().st_size} bytes)"
        else:
            checks["stream_file"] = "missing (will be created on first write)"
    except Exception as e:
        checks["stream_file"] = f"error: {e}"
    # Gemini check
    checks["gemini_configured"] = bool(settings.gemini_api_key)
    # Overall
    overall = "online" if checks["database"] == "ok" else "degraded"
    return {"status": overall, "service": "siliconpulse-backend", "checks": checks, "uptime_seconds": int(time.time() - START_TIME)}


@app.get("/metrics")
async def metrics():
    uptime = int(time.time() - START_TIME)
    # Stream stats
    stream_path = settings.resolved_data_path
    stream_size = stream_path.stat().st_size if stream_path.exists() else 0
    # DB stats
    try:
        conn = get_db_connection()
        cur = conn.execute("SELECT COUNT(*) FROM seen_events")
        row = cur.fetchone()
        seen_count = row[0] if row else 0
    except Exception:
        seen_count = -1
    return {
        "uptime_seconds": uptime,
        "requests_total": REQUEST_COUNT,
        "errors_total": ERROR_COUNT,
        "stream_file_bytes": stream_size,
        "dedup_seen_events": seen_count,
        "timestamp": now_ts(),
    }
