import os
import json
import hashlib
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

import httpx

from ..settings import settings
from ..utils import deduplicate_and_append, get_current_timestamp
from ..company_dict import COMPANY_DICT

logger = logging.getLogger(__name__)

NEWSDATA_API_KEY = os.getenv("NEWSDATA_API_KEY", "")
NEWSAPI_API_KEY = os.getenv("NEWSAPI_API_KEY", "")
GNEWS_API_KEY = os.getenv("GNEWS_API_KEY", "")
MEDIASTACK_API_KEY = os.getenv("MEDIASTACK_API_KEY", "")

TIMEOUT_SECONDS = 3
CACHE_TTL_SECONDS = 45

_cache: dict[str, tuple[list[dict], datetime]] = {}

SIGNAL_QUERIES = [
    "semiconductor chip manufacturing",
    "NVIDIA TSMC Intel AMD AI GPU",
    "Apple Samsung chip supply chain",
    "Google Meta Microsoft AI infrastructure",
    "ASML EUV lithography fab",
    "chip shortage export controls CHIPS act",
]


def _map_company(text: str) -> Optional[str]:
    if not text:
        return None
    text_lower = text.lower()
    for company, data in COMPANY_DICT.items():
        if company.lower() in text_lower:
            return company
        for alias in data.get("aliases", []):
            if alias.lower() in text_lower:
                return company
    return None


def _classify_event(text: str) -> str:
    t = text.lower()
    if any(w in t for w in ["acquired", "acquisition", "acqu", "bought", "deal", "merger"]):
        return "m_and_a"
    if any(w in t for w in ["partnership", "partner", "collaborate", "joint", "agreement"]):
        return "contract"
    if any(w in t for w in ["launched", "launch", "unveiled", "announce", "release", "open-source"]):
        return "product_launch"
    if any(w in t for w in ["produce", "production", "manufacturing", "fab", "yield", "fabrication"]):
        return "supply_chain"
    if any(w in t for w in ["supply", "shortage", "capacity", "export control", "sanction"]):
        return "supply_chain"
    if any(w in t for w in ["earnings", "revenue", "profit", "quarter", "stock"]):
        return "financial"
    if any(w in t for w in ["ai ", "artificial intelligence", "model", "gpt", "llama", "gemini"]):
        return "product_launch"
    return "general"


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
        "event_type": article.get("event_type") or _classify_event(text),
    }


# ---------------------------------------------------------------------------
# Individual API fetchers
# ---------------------------------------------------------------------------

async def fetch_newsdata(query: str) -> list[dict]:
    if not NEWSDATA_API_KEY:
        return []
    url = "https://newsdata.io/api/1/news"
    params = {"apikey": NEWSDATA_API_KEY, "q": query, "language": "en", "size": 10}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("results", []):
                results.append(_normalize({
                    "timestamp": item.get("pubDate") or _now_iso(),
                    "source": "NewsData.io",
                    "title": item.get("title") or "",
                    "snippet": item.get("description") or item.get("content") or "",
                    "url": item.get("link") or "",
                }))
            return results
    except Exception as exc:
        logger.warning(f"NewsData.io fetch failed for '{query}': {exc}")
        return []


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


async def fetch_gnews(query: str) -> list[dict]:
    if not GNEWS_API_KEY:
        return []
    url = "https://gnews.io/api/v4/search"
    params = {"token": GNEWS_API_KEY, "q": query, "lang": "en", "max": 10}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("articles", []):
                results.append(_normalize({
                    "timestamp": item.get("publishedAt") or _now_iso(),
                    "source": "GNews",
                    "title": item.get("title") or "",
                    "snippet": item.get("description") or "",
                    "url": item.get("url") or "",
                }))
            return results
    except Exception as exc:
        logger.warning(f"GNews fetch failed for '{query}': {exc}")
        return []


async def fetch_mediastack(query: str) -> list[dict]:
    if not MEDIASTACK_API_KEY:
        return []
    url = "https://api.mediastack.com/v1/news"
    params = {"access_key": MEDIASTACK_API_KEY, "keywords": query, "languages": "en", "limit": 10}
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_SECONDS) as client:
            resp = await client.get(url, params=params)
            resp.raise_for_status()
            data = resp.json()
            results = []
            for item in data.get("data", []):
                results.append(_normalize({
                    "timestamp": item.get("published_at") or _now_iso(),
                    "source": "Mediastack",
                    "title": item.get("title") or "",
                    "snippet": item.get("description") or "",
                    "url": item.get("url") or "",
                }))
            return results
    except Exception as exc:
        logger.warning(f"Mediastack fetch failed for '{query}': {exc}")
        return []


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------

async def fetch_all_sources(query: str) -> list[dict]:
    results = await asyncio.gather(
        fetch_newsdata(query),
        fetch_newsapi(query),
        fetch_gnews(query),
        fetch_mediastack(query),
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

async def async_pull_newsdata() -> int:
    all_articles = []
    for q in SIGNAL_QUERIES[:2]:
        all_articles.extend(await fetch_newsdata(q))
    return deduplicate_and_append(all_articles, settings.resolved_data_path)


async def async_pull_newsapi() -> int:
    all_articles = []
    for q in SIGNAL_QUERIES[:2]:
        all_articles.extend(await fetch_newsapi(q))
    return deduplicate_and_append(all_articles, settings.resolved_data_path)


async def async_pull_gnews() -> int:
    all_articles = []
    for q in SIGNAL_QUERIES[:2]:
        all_articles.extend(await fetch_gnews(q))
    return deduplicate_and_append(all_articles, settings.resolved_data_path)


async def async_pull_mediastack() -> int:
    all_articles = []
    for q in SIGNAL_QUERIES[:2]:
        all_articles.extend(await fetch_mediastack(q))
    return deduplicate_and_append(all_articles, settings.resolved_data_path)


def pull_newsdata() -> int:
    try:
        return asyncio.run(async_pull_newsdata())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_pull_newsdata())
        finally:
            loop.close()


def pull_newsapi() -> int:
    try:
        return asyncio.run(async_pull_newsapi())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_pull_newsapi())
        finally:
            loop.close()


def pull_gnews() -> int:
    try:
        return asyncio.run(async_pull_gnews())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_pull_gnews())
        finally:
            loop.close()


def pull_mediastack() -> int:
    try:
        return asyncio.run(async_pull_mediastack())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(async_pull_mediastack())
        finally:
            loop.close()
