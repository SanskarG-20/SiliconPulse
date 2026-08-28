"""
Ingestion routes for PDF and SEC filings.
"""

import logging

from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile

from ..core.auth import get_current_user
from ..core.limiter import limiter
from ..services.ingestion_pipeline import ingest_pdf_bytes, ingest_sec_filings

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/pdf")
@limiter.limit("10/minute")
async def ingest_pdf(
    request: Request,
    file: UploadFile = File(..., description="PDF file to ingest (max 10MB)"),
    user=Depends(get_current_user),
):
    """
    Upload a PDF (earnings report, etc.) -> text -> LLM events -> stream.
    Accepts: application/pdf, max 10MB.
    """
    # Validate file
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    content = await file.read()
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF too large (max 10MB)")

    if len(content) == 0:
        raise HTTPException(status_code=400, detail="Empty PDF file")

    # Ingest
    result = await ingest_pdf_bytes(
        pdf_bytes=content,
        source="PDFUpload",
        filename=file.filename,
        use_vision=False,  # set True to enable chart vision (costs more)
    )

    if result["status"] == "error":
        raise HTTPException(status_code=500, detail=result.get("message", "PDF ingestion failed"))

    return result


@router.post("/sec")
@limiter.limit("5/minute")
async def ingest_sec(
    request: Request,
    days_back: int = 3,
    user=Depends(get_current_user),
):
    """
    Trigger SEC 8-K ingestion for tracked tickers (last N days, default 3).
    """
    if days_back < 1 or days_back > 30:
        raise HTTPException(status_code=400, detail="days_back must be 1..30")

    result = await ingest_sec_filings(days_back=days_back)
    return result
