"""
Tests for SEC filings service via Finnhub API.
Mocked API responses for reliable testing.
"""
import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

from fastapi.testclient import TestClient

from app.main import app
from app.services.sec_filings import SECFilingsService

client = TestClient(app)


def test_sec_filings_fetch_company():
    """Test fetching 8-K filings for a single company."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {
        "filings": [
            {
                "title": "NVIDIA 8-K: Earnings Release",
                "description": "NVIDIA reports Q2 earnings",
                "filed_at": "2026-08-20T12:00:00Z",
                "url": "https://sec.gov/...",
                "form_type": "8-K",
            }
        ]
    }
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.aclose = AsyncMock(return_value=None)

    async def test():
        async with SECFilingsService() as service:
            service.api_key = "test_key"
            service.client = mock_client
            filings = await service.fetch_company_filings(
                "NVDA",
                datetime(2026, 8, 1),
                datetime(2026, 8, 26),
            )
            assert len(filings) == 1
            assert filings[0]["symbol"] == "NVDA"
            assert filings[0]["company"] == "NVIDIA"

    asyncio.run(test())


def test_sec_filings_multiple_companies():
    """Test fetching filings for multiple companies."""
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"filings": []}
    mock_client = AsyncMock()
    mock_client.get.return_value = mock_response
    mock_client.aclose = AsyncMock(return_value=None)

    async def test():
        async with SECFilingsService() as service:
            service.api_key = "test_key"
            service.client = mock_client
            filings = await service.fetch_multiple_companies(
                ["NVDA", "TSM"], days_back=7
            )
            assert isinstance(filings, list)

    asyncio.run(test())


def test_sec_filings_no_api_key():
    """Test graceful handling when no API key is configured."""
    with patch.dict("os.environ", {"FINNHUB_API_KEY": ""}, clear=True):
        import importlib

        from app.services import sec_filings
        importlib.reload(sec_filings)
        service = sec_filings.SECFilingsService()
        assert service.api_key == ""
        assert service.client is None


if __name__ == "__main__":
    asyncio.run(test_sec_filings_fetch_company())
    asyncio.run(test_sec_filings_multiple_companies())
    test_sec_filings_no_api_key()
    print("All SEC filings tests passed!")
