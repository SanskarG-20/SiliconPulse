"""
Video intelligence endpoint — serves YouTube video feed for the dashboard.
"""
import logging

from fastapi import APIRouter, Depends, Query, Request

from ..core.auth import get_current_user
from ..core.limiter import limiter
from ..services.youtube_service import fetch_youtube_videos

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/videos")
@limiter.limit("15/minute")
async def get_videos(
    request: Request,
    query: str = Query(default=None, description="Search query for videos"),
    category: str = Query(default="all", description="Video category filter"),
    limit: int = Query(default=8, ge=1, le=12, description="Maximum number of videos"),
    user=Depends(get_current_user),
):
    """Fetch recent tech/semiconductor/AI YouTube videos."""
    try:
        videos = await fetch_youtube_videos(query=query, category=category, limit=limit)
        return {"videos": videos}
    except Exception as e:
        logger.error(f"Videos endpoint error: {e}")
        return {"videos": []}
