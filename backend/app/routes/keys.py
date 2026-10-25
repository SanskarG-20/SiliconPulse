"""API key management for bots/CI (Phase 2.4). Raw key shown once at creation."""
import hashlib
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field

from ..core.auth import get_current_user
from ..core.limiter import limiter
from ..supabase_client import (
    create_api_key,
    ensure_user,
    is_supabase_enabled,
    list_api_keys,
    revoke_api_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


class KeyCreateRequest(BaseModel):
    name: str = Field(default="default", max_length=80)


@router.get("/keys")
async def list_keys(user=Depends(get_current_user)):
    return {"keys": list_api_keys(user.get("user_id", "")), "persisted": is_supabase_enabled()}


@router.post("/keys")
@limiter.limit("10/minute")
async def create_key(request: Request, body: KeyCreateRequest, user=Depends(get_current_user)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not is_supabase_enabled():
        raise HTTPException(status_code=503, detail="API keys unavailable (persistence not configured)")
    ensure_user(user_id, user.get("email"))
    raw_key = f"sp_live_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    row = create_api_key(user_id, body.name.strip() or "default", key_hash, raw_key[:14])
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create API key")
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "key": raw_key,
        "prefix": raw_key[:14],
        "warning": "Store this key now — it is never shown again. Send it in the X-API-Key header.",
    }


@router.delete("/keys/{key_id}")
async def delete_key(key_id: str, user=Depends(get_current_user)):
    revoke_api_key(user.get("user_id", ""), key_id)
    return {"keys": list_api_keys(user.get("user_id", "")), "revoked": key_id}
