import time
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from .routes import router
from .models import QueryResponse
from .utils import now_ts
from .settings import settings
from .storage import init_db
from .scheduler import start_scheduler, stop_scheduler

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title=settings.app_name,
    description="Strategic Intelligence Backend",
    version="1.0.0"
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Global Exception Handler
# Global Exception Handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
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

@app.on_event("startup")
async def startup_event():
    logger.info("Starting up SiliconPulse API...")
    logger.info(f"Using DATA_STREAM_PATH={settings.resolved_data_path}")
    init_db()
    logger.info("Database initialized")
    start_scheduler()
    logger.info("Real-time data scheduler started")

@app.on_event("shutdown")
async def shutdown_event():
    logger.info("Shutting down SiliconPulse API...")
    stop_scheduler()
    logger.info("Scheduler stopped")

# Include API routes with /api prefix
app.include_router(router, prefix="/api", tags=["api"])

@app.get("/")
async def root():
    return {"message": "SiliconPulse backend running"}

@app.get("/health")
async def health():
    return {"status": "online", "service": "siliconpulse-backend"}
