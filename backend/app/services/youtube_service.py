"""
YouTube Data API v3 service for Intelligence Videos.
Fetches recent tech/semiconductor/AI videos with in-memory caching.
"""
from __future__ import annotations

import hashlib
import logging
import time
from typing import Optional

import httpx
from pydantic import BaseModel

from app.settings import settings

logger = logging.getLogger(__name__)

YOUTUBE_SEARCH_URL = "https://www.googleapis.com/youtube/v3/search"

# --- Cache: 30-minute TTL to protect API quota ---
_cache: dict[str, tuple[float, list[dict]]] = {}
CACHE_TTL_SECONDS = 1800  # 30 minutes


def _cache_key(query: str, category: str, limit: int) -> str:
    raw = f"{query}:{category}:{limit}".lower().strip()
    return hashlib.md5(raw.encode()).hexdigest()


def _get_cached(key: str) -> list[dict] | None:
    if key in _cache:
        ts, data = _cache[key]
        if time.time() - ts < CACHE_TTL_SECONDS:
            return data
        del _cache[key]
    return None


def _set_cached(key: str, data: list[dict]) -> None:
    # Limit cache size to prevent memory growth
    if len(_cache) > 50:
        oldest_key = min(_cache, key=lambda k: _cache[k][0])
        del _cache[oldest_key]
    _cache[key] = (time.time(), data)


# --- Category -> search term mapping ---
CATEGORY_QUERIES: dict[str, str] = {
    "all": "latest technology semiconductor AI",
    "ai": "artificial intelligence AI latest news",
    "semiconductor": "semiconductor chip manufacturing latest",
    "product_launch": "new technology product launch announcement",
    "gpu": "GPU graphics card latest launch",
    "supply_chain": "semiconductor supply chain latest",
    "company_update": "tech company earnings update latest",
}

# --- Default rotating queries for general feed ---
DEFAULT_QUERIES = [
    "NVIDIA latest AI GPU",
    "TSMC semiconductor technology",
    "AMD latest product launch",
    "Intel technology update",
    "AI chip semiconductor latest",
    "semiconductor industry news",
    "latest technology product launch",
    "OpenAI latest announcement",
]

# Rotate through defaults based on hour of day
def _get_default_query() -> str:
    idx = int(time.time() // 3600) % len(DEFAULT_QUERIES)
    return DEFAULT_QUERIES[idx]


# --- Pydantic schema ---
class VideoItem(BaseModel):
    video_id: str
    title: str
    description: str
    thumbnail: str
    channel: str
    published_at: str
    url: str
    category: str = "general"


async def fetch_youtube_videos(
    query: Optional[str] = None,
    category: str = "all",
    limit: int = 8,
) -> list[dict]:
    """
    Fetch YouTube videos for a given query/category.
    Returns normalized list of video dicts. Never raises — returns [] on failure.
    """
    if not settings.youtube_api_key:
        logger.warning("YouTube API key not configured — skipping video fetch")
        return []

    # Clamp limit
    limit = min(max(limit, 1), 12)

    # Build search query
    if query and query.strip():
        search_query = f"{query.strip()} technology"
    elif category in CATEGORY_QUERIES:
        search_query = CATEGORY_QUERIES[category]
    else:
        search_query = _get_default_query()

    # Check cache
    cache_key = _cache_key(search_query, category, limit)
    cached = _get_cached(cache_key)
    if cached is not None:
        logger.debug(f"YouTube cache hit for '{search_query}'")
        return cached[:limit]

    # Call YouTube Data API v3
    try:
        params = {
            "part": "snippet",
            "q": search_query,
            "type": "video",
            "order": "date",
            "relevanceLanguage": "en",
            "maxResults": limit,
            "key": settings.youtube_api_key,
        }

        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.get(YOUTUBE_SEARCH_URL, params=params)

        if response.status_code == 403:
            logger.warning("YouTube API quota exceeded or forbidden")
            return []

        if response.status_code != 200:
            logger.warning(f"YouTube API returned {response.status_code}: {response.text[:200]}")
            return []

        data = response.json()
        items = data.get("items", [])

        videos = []
        for item in items:
            try:
                snippet = item.get("snippet", {})
                video_id = item.get("id", {}).get("videoId", "")
                if not video_id:
                    continue

                # Pick best thumbnail available
                thumbnails = snippet.get("thumbnails", {})
                thumbnail_url = (
                    thumbnails.get("high", {}).get("url")
                    or thumbnails.get("medium", {}).get("url")
                    or thumbnails.get("default", {}).get("url", "")
                )

                video = VideoItem(
                    video_id=video_id,
                    title=snippet.get("title", "Untitled"),
                    description=snippet.get("description", ""),
                    thumbnail=thumbnail_url,
                    channel=snippet.get("channelTitle", "Unknown Channel"),
                    published_at=snippet.get("publishedAt", ""),
                    url=f"https://www.youtube.com/watch?v={video_id}",
                    category=category,
                )
                videos.append(video.model_dump())
            except Exception as e:
                logger.debug(f"Skipping malformed video item: {e}")
                continue

        # Cache the results
        _set_cached(cache_key, videos)
        logger.info(f"YouTube: fetched {len(videos)} videos for '{search_query}'")
        return videos

    except httpx.TimeoutException:
        logger.warning("YouTube API request timed out")
        return []
    except Exception as e:
        logger.error(f"YouTube API error: {e}")
        return []
