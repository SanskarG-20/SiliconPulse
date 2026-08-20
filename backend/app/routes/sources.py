import asyncio
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request

from ..company_dict import COMPANY_DICT
from ..core.auth import get_current_user
from ..core.limiter import limiter
from ..models import SourceVerifyItem, SourceVerifyResponse
from ..services.news_sources import async_pull_newsapi, ingest_news_stream
from ..settings import settings
from ..sources.gdelt_source import pull_gdelt_signals
from ..sources.hackernews_source import pull_hn_signals
from ..utils import get_trust_info, safe_read_jsonl

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.post("/newsapi/pull")
@limiter.limit("5/minute")
async def pull_newsapi_endpoint(request: Request):
    """Trigger NewsAPI signal pull"""
    try:
        count = await async_pull_newsapi()
        return {"status": "ok", "source": "NewsAPI", "pulled": count, "timestamp": datetime.utcnow().isoformat() + "Z"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.post("/pull_all")
@limiter.limit("5/minute")
async def pull_all_sources(request: Request):
    """Trigger all signal sources (News APIs + GDELT + HackerNews)"""
    try:
        news_result, gdelt_count, hn_count = await asyncio.gather(
            ingest_news_stream(),
            asyncio.to_thread(pull_gdelt_signals),
            asyncio.to_thread(pull_hn_signals),
        )
        return {
            "status": "ok",
            "pulled": {
                "NewsAPIs": news_result,
                "GDELT": gdelt_count or 0,
                "HackerNews": hn_count or 0
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/verify", response_model=SourceVerifyResponse)
async def verify_sources(query: str):
    """
    Verify sources for a given query.
    Re-runs a quick retrieval to identify sources and assign trust levels.
    """
    try:
        data_path = settings.resolved_data_path
        events = safe_read_jsonl(data_path, limit=settings.max_events_to_scan, freshness_hours=settings.freshness_hours)

        raw_keywords = [kw.lower() for kw in query.split() if len(kw) > 2]
        query_keywords = set(raw_keywords)

        for company, data in COMPANY_DICT.items():
            aliases = [a.lower() for a in data.get("aliases", [])]
            aliases.append(company.lower())
            if any(kw in aliases for kw in raw_keywords):
                query_keywords.update(aliases)

        verified_sources = []
        seen_titles = set()

        for event in events:
            title = event.get("title", "").lower()
            content = event.get("content", "").lower()

            if any(kw in title or kw in content for kw in query_keywords):
                if event.get("title") not in seen_titles:
                    seen_titles.add(event.get("title"))

                    source_name = event.get("source", "Unknown")
                    trust_info = get_trust_info(source_name)

                    verified_sources.append(SourceVerifyItem(
                        timestamp=event.get("timestamp"),
                        source=source_name,
                        title=event.get("title", "Untitled"),
                        url=event.get("url"),
                        trust_level=trust_info["trust_level"],
                        reason=trust_info["reason"]
                    ))

            if len(verified_sources) >= 10:
                break

        return SourceVerifyResponse(
            query=query,
            sources=verified_sources
        )

    except Exception as e:
        logger = __import__('logging').getLogger(__name__)
        logger.error(f"Source verification failed: {e}")
        return SourceVerifyResponse(query=query, sources=[])
