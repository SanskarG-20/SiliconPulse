"""
SEC EDGAR 8-K filing ingestion via Finnhub API.
Fetches recent 8-K filings for tracked companies and extracts structured events.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

import httpx

logger = logging.getLogger(__name__)

# Mapping of common ticker symbols to company names for 8-K filtering
# In production, this would be a more comprehensive mapping or database
TICKER_COMPANY_MAP = {
    "NVDA": "NVIDIA",
    "TSM": "TSMC",
    "INTC": "Intel",
    "AMD": "AMD",
    "AAPL": "Apple",
    "GOOGL": "Google",
    "MSFT": "Microsoft",
    "AMZN": "Amazon",
    "META": "Meta",
    "TSLA": "Tesla",
    "ASML": "ASML",
    "AMAT": "Applied Materials",
    "LRCX": "Lam Research",
    "KLAC": "KLA Corporation",
    "MU": "Micron",
    "AVGO": "Broadcom",
    "QCOM": "Qualcomm",
    "TXN": "Texas Instruments",
    "ADI": "Analog Devices",
    "MRVL": "Marvell",
    "NXPI": "NXP Semiconductors",
    "ON": "onsemi",
    "SWKS": "Skyworks",
    "QRVO": "Qorvo",
    "SMH": "Semiconductor ETF",  # for ETF holdings
    "SOXX": "Semiconductor ETF",
}

FINNHUB_API_URL = "https://finnhub.io/api/v1"


class SECFilingsService:
    """Service to fetch and parse SEC 8-K filings via Finnhub API."""

    def __init__(self):
        self.api_key = os.getenv("FINNHUB_API_KEY", "")
        self.client: httpx.AsyncClient | None = None

    async def __aenter__(self):
        if self.api_key:
            self.client = httpx.AsyncClient(timeout=30.0)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.client:
            await self.client.aclose()

    async def fetch_company_filings(
        self, symbol: str, from_date: datetime, to_date: datetime
    ) -> list[dict]:
        """
        Fetch 8-K filings for a company within date range.
        Returns list of filing dicts with metadata.
        """
        if not self.client or not self.api_key:
            logger.warning("Finnhub API key not configured, skipping SEC filings")
            return []

        try:
            params = {
                "symbol": symbol,
                "from": from_date.strftime("%Y-%m-%d"),
                "to": to_date.strftime("%Y-%m-%d"),
                "form_type": "8-K",
                "token": self.api_key,
            }

            response = await self.client.get(
                f"{FINNHUB_API_URL}/stock/filings", params=params
            )
            response.raise_for_status()
            data = response.json()

            filings = data.get("filings", [])
            for filing in filings:
                filing["symbol"] = symbol
                filing["company"] = TICKER_COMPANY_MAP.get(symbol, symbol)
            logger.info(f"Fetched {len(filings)} 8-K filings for {symbol}")
            return filings

        except Exception as e:
            logger.warning(f"Failed to fetch 8-K filings for {symbol}: {e}")
            return []

    async def fetch_multiple_companies(
        self, symbols: list[str], days_back: int = 7
    ) -> list[dict]:
        """Fetch 8-K filings for multiple companies over the last N days."""
        if not self.client or not self.api_key:
            return []

        to_date = datetime.utcnow()
        from_date = to_date - timedelta(days=days_back)

        all_filings = []
        for symbol in symbols:
            try:
                filings = await self.fetch_company_filings(symbol, from_date, to_date)
                for filing in filings:
                    filing["symbol"] = symbol
                    filing["company"] = TICKER_COMPANY_MAP.get(symbol, symbol)
                all_filings.extend(filings)
            except Exception as e:
                logger.warning(f"Error fetching filings for {symbol}: {e}")

        # Sort by filing date descending
        all_filings.sort(key=lambda x: x.get("filed_at", ""), reverse=True)
        return all_filings

    def extract_filing_text(self, filing: dict) -> str:
        """Extract text content from filing metadata."""
        parts = []
        if filing.get("title"):
            parts.append(filing["title"])
        if filing.get("description"):
            parts.append(filing["description"])
        if filing.get("url"):
            parts.append(f"Source: {filing['url']}")
        return "\n".join(parts) if parts else ""


sec_filings_service = SECFilingsService()
