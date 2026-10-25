"""API key management for bots/CI (Phase 2.4). Raw key shown once at creation."""
import hashlib
import logging
import secrets
from datetime import datetime, timedelta, timezone

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
    rotate_api_key,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


class KeyCreateRequest(BaseModel):
    name: str = Field(default="default", max_length=80)
    scopes: list[str] = Field(default_factory=lambda: ["signals:read", "query:read", "trends:read", "compare:read", "reports:generate"])
    expires_in_days: int = Field(default=90, ge=1, le=365)


ALLOWED_SCOPES = {"signals:read", "query:read", "trends:read", "compare:read", "reports:generate"}


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
    if not body.scopes or not set(body.scopes).issubset(ALLOWED_SCOPES):
        raise HTTPException(status_code=422, detail="One or more API key scopes are invalid")
    ensure_user(user_id, user.get("email"))
    raw_key = f"sp_live_{secrets.token_hex(24)}"
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    expires_at = (datetime.now(timezone.utc) + timedelta(days=body.expires_in_days)).isoformat()
    row = create_api_key(user_id, body.name.strip() or "default", key_hash, raw_key[:14], body.scopes, expires_at)
    if not row:
        raise HTTPException(status_code=500, detail="Failed to create API key")
    return {
        "id": row.get("id"),
        "name": row.get("name"),
        "key": raw_key,
        "prefix": raw_key[:14],
        "scopes": body.scopes,
        "expires_at": expires_at,
        "warning": "Store this key now — it is never shown again. Send it in the X-API-Key header.",
    }


@router.post("/keys/{key_id}/rotate")
@limiter.limit("10/minute")
async def rotate_key(request: Request, key_id: str, user=Depends(get_current_user)):
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    if not is_supabase_enabled():
        raise HTTPException(status_code=503, detail="API keys unavailable (persistence not configured)")
    raw_key = f"sp_live_{secrets.token_hex(24)}"
    expires_at = (datetime.now(timezone.utc) + timedelta(days=90)).isoformat()
    row = rotate_api_key(user_id, key_id, hashlib.sha256(raw_key.encode()).hexdigest(), raw_key[:14], expires_at)
    if not row:
        raise HTTPException(status_code=404, detail="API key not found or rotation failed")
    return {"id": row.get("id"), "name": row.get("name"), "key": raw_key, "prefix": raw_key[:14], "scopes": row.get("scopes", []), "expires_at": expires_at, "warning": "Store this key now — it is never shown again. The previous key has been revoked."}


@router.delete("/keys/{key_id}")
async def delete_key(key_id: str, user=Depends(get_current_user)):
    revoke_api_key(user.get("user_id", ""), key_id)
    return {"keys": list_api_keys(user.get("user_id", "")), "revoked": key_id}
