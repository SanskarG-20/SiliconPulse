"""Brief annotations (Phase 3.1). Public read on public briefs; auth to post/delete own."""
import logging
import html
import re
import unicodedata

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.auth import get_current_user
from ..core.limiter import limiter
from ..core.tenant import require_public_brief
from ..supabase_client import (
    add_brief_comment,
    delete_brief_comment,
    ensure_user,
    is_supabase_enabled,
    list_brief_comments,
)

logger = logging.getLogger(__name__)

# No global auth dep: thread read is public, writes require auth per-route.
router = APIRouter()


class CommentPost(BaseModel):
    body: str = Field(..., min_length=1, max_length=2000)


@router.get("/briefs/public/{brief_id}/comments")
@limiter.limit("60/minute")
async def get_comments(request: Request, brief_id: str, limit: int = 50):
    require_public_brief(brief_id)
    return {"comments": list_brief_comments(brief_id, limit=limit)}


@router.post("/briefs/{brief_id}/comments")
@limiter.limit("10/minute")
async def post_comment(request: Request, brief_id: str, body: CommentPost, user=Depends(get_current_user)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    require_public_brief(brief_id)
    text = unicodedata.normalize("NFKC", html.unescape(body.body or ""))
    text = re.sub(r"<[^>]*>", " ", text)
    text = "".join(ch for ch in text if ch in "\n\t" or not unicodedata.category(ch).startswith("C"))
    text = re.sub(r"[ \t]+", " ", text).strip()
    if not text:
        raise HTTPException(status_code=400, detail="Comment body required")
    ensure_user(user_id, user.get("email"))
    row = add_brief_comment(brief_id, user_id, text)
    if row is None and is_supabase_enabled():
        raise HTTPException(status_code=500, detail="Failed to save comment")
    if row is None:
        raise HTTPException(status_code=503, detail="Comments unavailable (persistence not configured)")
    return {"comment": {"id": row.get("id"), "user_id": user_id, "body": row.get("body"), "created_at": row.get("created_at")}}


@router.delete("/comments/{comment_id}")
async def delete_comment(comment_id: str, user=Depends(get_current_user)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    delete_brief_comment(comment_id, user_id)
    return {"deleted": comment_id}
