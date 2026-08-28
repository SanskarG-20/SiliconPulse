"""
Tests for PDF/SEC ingestion routes and pipelines.
Covers edge cases: empty, oversized, non-PDF, SEC bounds, LLM fallback.
"""
from unittest.mock import AsyncMock, patch, MagicMock
from pathlib import Path
import tempfile
import io

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}
client = TestClient(app)


def test_ingest_pdf_rejects_non_pdf():
    files = {"file": ("report.txt", b"not a pdf", "text/plain")}
    resp = client.post("/api/ingest/pdf", files=files)
    assert resp.status_code == 400
    assert "Only PDF" in resp.json()["detail"]


def test_ingest_pdf_rejects_empty():
    # Minimal PDF header but empty after read? Use 0 bytes
    files = {"file": ("empty.pdf", b"", "application/pdf")}
    resp = client.post("/api/ingest/pdf", files=files)
    assert resp.status_code == 400
    assert "Empty" in resp.json()["detail"]


def test_ingest_pdf_rejects_oversized():
    big = b"%PDF-" + b"x" * (10 * 1024 * 1024 + 1)
    files = {"file": ("big.pdf", big, "application/pdf")}
    resp = client.post("/api/ingest/pdf", files=files)
    assert resp.status_code == 400
    assert "too large" in resp.json()["detail"].lower()


def test_ingest_pdf_success_via_mock():
    fake_pdf = b"%PDF-1.4 fake content"
    with patch("app.routes.ingest.ingest_pdf_bytes", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = {"status": "ok", "filename": "test.pdf", "text_len": 100, "extracted_events": 2, "added": 2, "vector_enabled": False}
        files = {"file": ("test.pdf", fake_pdf, "application/pdf")}
        resp = client.post("/api/ingest/pdf", files=files)
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["added"] == 2
        mock_ingest.assert_called_once()


def test_ingest_pdf_pipeline_error_returns_500():
    fake_pdf = b"%PDF-1.4 fake"
    with patch("app.routes.ingest.ingest_pdf_bytes", new_callable=AsyncMock) as mock_ingest:
        mock_ingest.return_value = {"status": "error", "message": "No text extracted", "added": 0}
        files = {"file": ("test.pdf", fake_pdf, "application/pdf")}
        resp = client.post("/api/ingest/pdf", files=files)
        assert resp.status_code == 500


def test_ingest_sec_bounds():
    resp = client.post("/api/ingest/sec?days_back=0")
    assert resp.status_code == 400
    resp = client.post("/api/ingest/sec?days_back=31")
    assert resp.status_code == 400
    resp = client.post("/api/ingest/sec?days_back=3")
    # With no Finnhub key, returns ok with fetched 0 (graceful no-op)
    # Mock to avoid real network
    with patch("app.routes.ingest.ingest_sec_filings", new_callable=AsyncMock) as mock_sec:
        mock_sec.return_value = {"status": "ok", "fetched": 0, "added": 0, "symbols": ["NVDA"]}
        resp = client.post("/api/ingest/sec?days_back=3")
        assert resp.status_code == 200


def test_ingest_sec_success_mock():
    with patch("app.routes.ingest.ingest_sec_filings", new_callable=AsyncMock) as mock_sec:
        mock_sec.return_value = {"status": "ok", "fetched": 2, "extracted_events": 4, "added": 3}
        resp = client.post("/api/ingest/sec?days_back=3")
        assert resp.status_code == 200
        assert resp.json()["added"] == 3


def test_pdf_parser_extract_text_empty_bytes():
    from app.services.pdf_parser import pdf_parser
    # Invalid PDF bytes should return "" gracefully, not raise
    text = pdf_parser.extract_text(b"not a pdf")
    assert isinstance(text, str)


def test_llm_extractor_no_key_returns_empty():
    from app.services.llm_extractor import extract_events_from_text
    import asyncio

    # Ensure no GEMINI_API_KEY
    with patch("app.services.llm_extractor.settings.gemini_api_key", ""):
        events = asyncio.run(extract_events_from_text("Some financial report about TSMC yield", source="Test"))
        assert events == []
