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


from pydantic import BaseModel, Field

class LLMEvent(BaseModel):
    title: str = Field(description="Concise event title, <100 chars")
    content: str = Field(description="2-3 sentence summary")
    event_type: str = Field(description="One of: financial, supply_chain, product_launch, m_and_a, contract, general")
    company: str = Field(description="Primary company name, or Unknown")
    confidence: str = Field(description="High, Medium, or Low")
    timestamp: str = Field(default="", description="Timestamp if available")
    url: str = Field(default="", description="URL if available")

class LLMGraphEdge(BaseModel):
    source: str = Field(description="Source company")
    target: str = Field(description="Target company")
    relation: str = Field(description="Relationship type, e.g., supplies, manufactures, equips, invests")
    weight: float = Field(default=1.0, description="Confidence or impact weight 0.0-1.0")
    details: str = Field(default="", description="Brief details about the relationship")

class LLMExtractionResult(BaseModel):
    events: list[LLMEvent]
    edges: list[LLMGraphEdge] = Field(default_factory=list, description="Extracted supply chain relationships")

EXTRACTION_PROMPT_TEMPLATE = """
You are SiliconPulse, an expert financial intelligence extractor for semiconductor & AI supply chain.

TASK: Extract structured events and supply chain relationships (edges) from the following document text.

DOCUMENT TEXT (truncated to {trunc_len} chars):
---
{text}
---

INSTRUCTIONS for EVENTS:
- Extract ALL distinct events that are material to semiconductor, AI, or tech supply chain.
- Focus especially on: earnings, revenue, guidance, capex, yield, capacity, fab, supply, foundry, acquisition, merger, product launch, contract, partnership.
- If no material events, return an empty events list.

INSTRUCTIONS for EDGES:
- Identify any stated supply chain relationships, partnerships, or investments between companies (e.g. ASML supplies TSMC, TSMC manufactures for NVIDIA).
- Return them as edges with source, target, relation, weight, and details.
- If no relationships are found, return an empty edges list.
"""


async def extract_events_from_text(
    text: str,
    source: str = "LLMExtractor",
    max_events: int = 5,
) -> tuple[list[dict], list[dict]]:
    """
    Extract structured events and edges from raw text via Gemini.
    Returns (events, edges).
    Gracefully returns ([], []) if no key or on failure.
    """
    if not text or not text.strip():
        return [], []

    if not settings.gemini_api_key:
        logger.warning("LLM extraction skipped: no GEMINI_API_KEY")
        return [], []

    # Truncate to fit context window
    trunc_len = 8000
    truncated = text[:trunc_len]

    prompt = EXTRACTION_PROMPT_TEMPLATE.format(text=truncated, trunc_len=trunc_len)

    try:
        raw = await gemini_client.generate_content_with_fallback(prompt, response_schema=LLMExtractionResult)

        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"LLM extraction invalid JSON: {raw[:500]}")
            return [], []

        events_data = data.get("events", [])
        if not isinstance(events_data, list):
            logger.warning(f"LLM extraction expected list in 'events', got {type(events_data)}")
            events_data = []

        edges_data = data.get("edges", [])
        if not isinstance(edges_data, list):
            edges_data = []

        events = []
        for item in events_data[:max_events]:
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

        edges = []
        for item in edges_data[:max_events]:
            if not isinstance(item, dict):
                continue
            source_c = str(item.get("source", "")).strip()
            target_c = str(item.get("target", "")).strip()
            relation = str(item.get("relation", "")).strip()
            if source_c and target_c and relation:
                edges.append({
                    "source": source_c,
                    "target": target_c,
                    "relation": relation,
                    "weight": float(item.get("weight", 1.0)),
                    "details": str(item.get("details", "")).strip()
                })

        logger.info(f"LLM extracted {len(events)} events and {len(edges)} edges from {len(truncated)} chars")
        return events, edges

    except Exception as e:
        logger.warning(f"LLM extraction failed: {e}")
        return [], []


async def extract_events_batch(
    texts: list[str], source: str = "LLMExtractor"
) -> list[dict]:
    """Extract events from multiple texts in parallel (best-effort). Returns only events."""
    import asyncio

    results = await asyncio.gather(
        *(extract_events_from_text(t, source=source) for t in texts), return_exceptions=True
    )
    all_events: list[dict] = []
    for r in results:
        if isinstance(r, tuple) and len(r) == 2:
            all_events.extend(r[0])
        elif isinstance(r, Exception):
            logger.warning(f"Batch extraction item failed: {r}")
    return all_events
