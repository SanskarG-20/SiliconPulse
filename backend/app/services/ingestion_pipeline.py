"""
Unified ingestion pipeline for PDF and SEC filings.
Takes raw documents -> text -> LLM events -> deduplicate_and_append.
"""

from __future__ import annotations

import logging

from app.services.llm_extractor import extract_events_from_text
from app.services.pdf_parser import pdf_parser
from app.services.sec_filings import SECFilingsService
from app.services.vector_store import is_available as vector_available
from app.settings import settings
from app.utils import deduplicate_and_append

logger = logging.getLogger(__name__)


async def ingest_pdf_bytes(
    pdf_bytes: bytes,
    source: str = "PDFUpload",
    filename: str = "unknown.pdf",
    use_vision: bool = False,
) -> dict:
    """
    Ingest a PDF (bytes) -> text -> LLM events -> vector store.
    Returns summary dict.
    """
    try:
        # Extract text
        if use_vision:
            extracted = await pdf_parser.extract_all(pdf_bytes, use_vision=True, context=filename)
            text = extracted.get("text", "") + "\n\n" + "\n".join(
                f"Table (p{t['page']}): {t['markdown']}" for t in extracted.get("tables", [])[:3]
            )
        else:
            text = pdf_parser.extract_text(pdf_bytes)
            tables = pdf_parser.extract_tables(pdf_bytes)
            if tables:
                text += "\n\n" + "\n".join(f"Table (p{t['page']}): {t['markdown']}" for t in tables[:3])

        if not text.strip():
            return {"status": "error", "message": "No text extracted from PDF", "added": 0}

        # LLM extraction
        events = await extract_events_from_text(text, source=source, max_events=10)
        if not events:
            return {"status": "empty", "message": "No material events extracted", "added": 0, "text_len": len(text)}

        # Deduplicate and append
        data_path = settings.resolved_data_path
        added = deduplicate_and_append(events, data_path)

        return {
            "status": "ok",
            "filename": filename,
            "text_len": len(text),
            "extracted_events": len(events),
            "added": added,
            "vector_enabled": vector_available(),
        }

    except Exception as e:
        logger.error(f"PDF ingestion failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "added": 0}


async def ingest_sec_filings(days_back: int = 3, symbols: list[str] | None = None) -> dict:
    """
    Fetch recent 8-K filings and ingest via LLM extraction.
    """
    if symbols is None:
        # Default to core semiconductor tickers
        symbols = ["NVDA", "TSM", "INTC", "AMD", "AAPL", "ASML", "MU", "AVGO", "QCOM"]

    try:
        async with SECFilingsService() as svc:
            filings = await svc.fetch_multiple_companies(symbols, days_back=days_back)

        if not filings:
            return {"status": "ok", "message": "No filings found", "fetched": 0, "added": 0}

        # For each filing, extract text and then LLM events
        total_added = 0
        total_events = 0
        for filing in filings[:10]:  # limit to 10 most recent
            # Use filing title+description as text; if SEC filing has URL, could fetch PDF but skip for now
            filing_text = f"{filing.get('title','')} {filing.get('description','')} {filing.get('url','')}".strip()
            if not filing_text:
                continue
            events = await extract_events_from_text(
                filing_text,
                source="SECFiling",
                max_events=3,
            )
            if events:
                # Tag with filing metadata
                for ev in events:
                    ev["url"] = filing.get("url", ev.get("url", ""))
                    # Preserve original filing timestamp
                    if filing.get("filed_at"):
                        ev["timestamp"] = filing["filed_at"]
                added = deduplicate_and_append(events, settings.resolved_data_path)
                total_added += added
                total_events += len(events)

        return {
            "status": "ok",
            "fetched": len(filings),
            "extracted_events": total_events,
            "added": total_added,
            "symbols": symbols,
        }

    except Exception as e:
        logger.error(f"SEC ingestion failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e), "added": 0}
