"""
LLM-based extraction service for financial/supply-chain events.
Takes raw text (PDF, SEC filing) and extracts structured event dicts via Gemini.
"""

from __future__ import annotations

import json
import logging

from app.services.gemini_client import gemini_client
from app.settings import settings
from app.utils import get_primary_company

logger = logging.getLogger(__name__)


EXTRACTION_PROMPT_TEMPLATE = """
You are SiliconPulse, an expert financial intelligence extractor for semiconductor & AI supply chain.

TASK: Extract structured events from the following document text.

DOCUMENT TEXT (truncated to {trunc_len} chars):
---
{text}
---

INSTRUCTIONS:
- Extract ALL distinct events that are material to semiconductor, AI, or tech supply chain.
- For each event, provide: title (concise, <100 chars), content (2-3 sentence summary), event_type (one of: financial, supply_chain, product_launch, m_and_a, contract, general), company (primary company name, or Unknown), and confidence (High/Medium/Low).
- Focus especially on: earnings, revenue, guidance, capex, yield, capacity, fab, supply, foundry, acquisition, merger, product launch, contract, partnership.
- If no material events, return empty list.

OUTPUT: Strictly valid JSON list, no markdown. Example:
[
  {{"title": "TSMC N2 yield hits 90%", "content": "TSMC reports 2nm yield milestone exceeding target...", "event_type": "supply_chain", "company": "TSMC", "confidence": "High"}},
  {{"title": "NVIDIA reports Q2 revenue $30B", "content": "NVIDIA beats estimates...", "event_type": "financial", "company": "NVIDIA", "confidence": "High"}}
]
"""


async def extract_events_from_text(
    text: str,
    source: str = "LLMExtractor",
    max_events: int = 5,
) -> list[dict]:
    """
    Extract structured events from raw text via Gemini.
    Returns list of event dicts compatible with deduplicate_and_append.
    Gracefully returns [] if no key or on failure.
    """
    if not text or not text.strip():
        return []

    if not settings.gemini_api_key:
        logger.warning("LLM extraction skipped: no GEMINI_API_KEY")
        return []

    # Truncate to fit context window
    trunc_len = 8000
    truncated = text[:trunc_len]

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(text=truncated, trunc_len=trunc_len)

    try:
        raw = await gemini_client.generate_content_with_fallback(prompt)

        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            # remove ```json and ```
            lines = raw.splitlines()
            # remove first line if ```json
            if lines[0].strip().startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            raw = "\n".join(lines).strip()

        # Parse JSON
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            # Try to extract JSON array from text
            start = raw.find("[")
            end = raw.rfind("]")
            if start != -1 and end != -1 and end > start:
                data = json.loads(raw[start : end + 1])
            else:
                logger.warning(f"LLM extraction invalid JSON: {raw[:500]}")
                return []

        if not isinstance(data, list):
            logger.warning(f"LLM extraction expected list, got {type(data)}")
            return []

        events = []
        for item in data[:max_events]:
            if not isinstance(item, dict):
                continue
            title = str(item.get("title", "")).strip()
            if not title:
                continue
            content = str(item.get("content", "")).strip() or title
            event_type = str(item.get("event_type", "general")).strip().lower() or "general"
            # Normalize event_type to allowed set
            allowed = {"financial", "supply_chain", "product_launch", "m_and_a", "contract", "general"}
            if event_type not in allowed:
                # Map common variants
                mapping = {
                    "manufacturing": "supply_chain",
                    "supply chain": "supply_chain",
                    "m_a": "m_and_a",
                    "acquisition": "m_and_a",
                    "launch": "product_launch",
                    "ai": "product_launch",
                }
                event_type = mapping.get(event_type, "general")

            company = str(item.get("company", "")).strip() or get_primary_company(title + " " + content) or "Unknown"

            events.append(
                {
                    "title": title[:200],
                    "content": content[:2000],
                    "timestamp": item.get("timestamp") or "",
                    "source": source,
                    "company": company,
                    "event_type": event_type,
                    "url": item.get("url", ""),
                }
            )

        logger.info(f"LLM extracted {len(events)} events from {len(truncated)} chars")
        return events

    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}")
        return []


async def extract_events_batch(
    texts: list[str], source: str = "LLMExtractor"
) -> list[dict]:
    """Extract events from multiple texts in parallel (best-effort)."""
    import asyncio

    results = await asyncio.gather(
        *(extract_events_from_text(t, source=source) for t in texts), return_exceptions=True
    )
    all_events: list[dict] = []
    for r in results:
        if isinstance(r, list):
            all_events.extend(r)
        elif isinstance(r, Exception):
            logger.warning(f"Batch extraction item failed: {r}")
    return all_events
