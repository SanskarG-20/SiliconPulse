"""
Embedding service using Google Gemini (gemini-embedding-001) with in-memory cache.
Falls back gracefully if API key is missing.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging

from app.settings import settings

logger = logging.getLogger(__name__)

EMBED_MODEL = "gemini-embedding-001"
EMBED_DIM = 768  # gemini-embedding-001 default output dimension

_cache: dict[str, list[float]] = {}
_cache_max = 5000


def _text_key(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


async def embed_texts(texts: list[str]) -> list[list[float] | None]:
    """
    Embed a batch of texts. Returns list aligned with input; None on failure per item.
    Uses cache; only sends cache misses to the API.
    """
    if not settings.gemini_api_key:
        logger.warning("Embedding skipped: no GEMINI_API_KEY")
        return [None] * len(texts)

    results: list[list[float] | None] = [None] * len(texts)
    misses: list[tuple[int, str]] = []
    for i, t in enumerate(texts):
        key = _text_key(t)
        if key in _cache:
            results[i] = _cache[key]
        else:
            misses.append((i, t))

    if not misses:
        return results

    try:
        from google import genai as genai_new

        client = genai_new.Client(api_key=settings.gemini_api_key)
        miss_texts = [t for _, t in misses]
        resp = await asyncio.wait_for(
            client.aio.models.embed_content(
                model=EMBED_MODEL,
                contents=miss_texts,
            ),
            timeout=15,
        )
        embeddings = getattr(resp, "embeddings", None) or []
        for (idx, txt), emb in zip(misses, embeddings):
            vec = getattr(emb, "values", None)
            if vec:
                key = _text_key(txt)
                if len(_cache) >= _cache_max:
                    # simple eviction: clear half
                    for k in list(_cache.keys())[: _cache_max // 2]:
                        _cache.pop(k, None)
                _cache[key] = vec
                results[idx] = vec
    except Exception as e:
        logger.warning(f"Embedding batch failed: {e}")

    return results


async def embed_text(text: str) -> list[float] | None:
    """Embed a single text."""
    res = await embed_texts([text])
    return res[0] if res else None


def cache_size() -> int:
    return len(_cache)
