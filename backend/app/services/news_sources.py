from __future__ import annotations

import asyncio
import hashlib
import logging
import os
from datetime import datetime

import httpx

from ..settings import settings
from ..utils import (
    classify_event_type,
    deduplicate_and_append,
    extract_companies,
)

logger = logging.getLogger(__name__)

NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY", "")
TIMEOUT_SECONDS = 3
CACHE_TTL_SECONDS = 45

_cache: dict[str, tuple[list[dict], datetime]] = {}

SIGNAL_QUERIES = [
    "tech startup funding",
    "AI startup launch",
    "semiconductor manufacturing company",
    "tech acquisition merger",
    "cloud infrastructure company",
    "new technology product announcement"
]


def _map_company(text: str) -> str | None:
    """Dynamically extract the primary company name from text using NLP/Regex heuristics."""
    companies = extract_companies(text)
    if companies:
        return companies[0]
    return None


def _hash_title_url(title: str, url: str) -> str:
    return hashlib.sha256(f"{title}|{url}".encode()).hexdigest()


def _now_iso() -> str:
    return datetime.utcnow().isoformat() + "Z"


def _normalize(article: dict) -> dict:
    title = article.get("title") or ""
    snippet = article.get("snippet") or ""
    url = article.get("url") or ""
    source = article.get("source") or "Unknown"
    timestamp = article.get("timestamp") or _now_iso()
    text = f"{title} {snippet}".strip()
    return {
        "timestamp": timestamp,
        "source": source,
        "title": title,
        "snippet": snippet,
        "content": snippet,
        "url": url,
        "company": article.get("company") or _map_company(text),
        "event_type": article.get("event_type") or classify_event_type(title, snippet),
    }


# ---------------------------------------------------------------------------
# Individual API fetchers
# ---------------------------------------------------------------------------

async def fetch_newsapi(query: str) -> list[dict]:
    if not NEWSAPI_API_KEY:
        return []
    url = "https://newsapi.org/v2/everything"
    params = {"apiKey": NEWSAPI_API_KEY, "q": query, "language": "en", "pageSize": 10, "sortBy": "publishedAt"}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("articles", []):
                results.append(_normalize({
                    "timestamp": item.get("publishedAt") or _now_iso(),
                    "source": "NewsAPI",
                    "title": item.get("title") or "",
                    "snippet": item.get("description") or item.get("content") or "",
                    "url": item.get("url") or "",
                }))
            return results
    except Exception as exc:
        logger.warning(f"NewsAPI fetch failed for '{query}': {exc}")
        return []



# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

async def fetch_all_sources(query: str) -> list[dict]:
    results = await asyncio.gather(
        fetch_newsapi(query),
        return_exceptions=True,
    )

    merged: list[dict] = []
    for r in results:
        if isinstance(r, list):
            for article in r:
                if isinstance(article, dict):
                    merged.append(article)

    seen: set[str] = set()
    deduped: list[dict] = []
    for article in merged:
        key = _hash_title_url(article.get("title", ""), article.get("url", ""))
        if key not in seen:
            seen.add(key)
            deduped.append(article)

    deduped.sort(key=lambda a: str(a.get("timestamp") or ""), reverse=True)
    return deduped[:20]


# ---------------------------------------------------------------------------
# Multi-query ingestion (for scheduler / pull_all)
# ---------------------------------------------------------------------------

async def ingest_news_stream() -> dict[str, int]:
    cache_key = "ingest_news_stream"
    now = datetime.utcnow()
    if cache_key in _cache:
        cached_data, cached_at = _cache[cache_key]
        if (now - cached_at).total_seconds() < CACHE_TTL_SECONDS:
            return {"total_fetched": len(cached_data), "new_added": 0, "cached": True}

    all_articles: list[dict] = []
    for query in SIGNAL_QUERIES:
        batch = await fetch_all_sources(query)
        all_articles.extend(batch)

    seen: set[str] = set()
    unique: list[dict] = []
    for article in all_articles:
        if not isinstance(article, dict):
            continue
        key = _hash_title_url(str(article.get("title", "")), str(article.get("url", "")))
        if key not in seen:
            seen.add(key)
            unique.append(article)

    unique.sort(key=lambda a: str(a.get("timestamp") or ""), reverse=True)
    top = unique[:50]

    added = deduplicate_and_append(top, settings.resolved_data_path)

    _cache[cache_key] = (top, now)

    logger.info(f"News ingestion complete: {added} new articles appended (from {len(top)} unique)")
    return {"total_fetched": len(top), "new_added": added}


def ingest_news_stream_sync() -> dict[str, int]:
    try:
        return asyncio.run(ingest_news_stream())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(ingest_news_stream())
        finally:
            loop.close()


# ---------------------------------------------------------------------------
# Individual pull helpers (for manual trigger endpoints)
# ---------------------------------------------------------------------------

async def async_pull_newsapi() -> int:
    all_articles = []
    for q in SIGNAL_QUERIES[:2]:
        all_articles.extend(await fetch_newsapi(q))
    return deduplicate_and_append(all_articles, settings.resolved_data_path)


def pull_newsapi() -> int:
    try:
        return asyncio.run(async_pull_newsapi())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_pull_newsapi())
        finally:
            loop.close()

