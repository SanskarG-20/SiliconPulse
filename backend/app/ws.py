"""
WebSocket endpoint for live signal push.
- Auth via Clerk JWT passed as ?token= query param (browsers can't set WS headers)
- Pushes signals every N seconds only when changed (hash compare)
- Falls back gracefully: client keeps SWR polling as backup
"""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging

import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from .settings import settings
from .utils import safe_read_jsonl

logger = logging.getLogger(__name__)
router = APIRouter()

PUSH_INTERVAL_SECONDS = 10


def _verify_ws_token(token: str | None) -> str | None:
    """Validate Clerk JWT from query param. Returns user_id or None."""
    if not token:
        return None
    try:
        jwks_client = jwt.PyJWKClient(f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json")
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        decode_args = {
            "jwt": token,
            "key": signing_key.key,
            "algorithms": ["RS256"],
            "issuer": settings.clerk_issuer.rstrip("/"),
        }
        if settings.clerk_audience:
            decode_args["audience"] = settings.clerk_audience
        else:
            decode_args["options"] = {"verify_aud": False}
        payload = jwt.decode(**decode_args)
        return payload.get("sub")
    except Exception as e:
        logger.warning(f"WS auth failed: {e}")
        return None


def _current_signals_payload() -> tuple[str, list[dict]]:
    """Read latest signals and return (content_hash, events)."""
    data_path = settings.resolved_data_path
    if not data_path.exists():
        return "empty", []
    events = safe_read_jsonl(data_path, limit=20, freshness_hours=settings.freshness_hours)
    digest = hashlib.sha256(json.dumps(events, sort_keys=True, default=str).encode()).hexdigest()
    return digest, events


@router.websocket("/ws/signals")
async def ws_signals(ws: WebSocket):
    """
    Live signals stream. Auth: ?token=<clerk_jwt>
    Server pushes full signal list whenever content changes (checked every PUSH_INTERVAL_SECONDS).
    Client sends "ping" -> server replies "pong" (keep-alive).
    """
    token = ws.query_params.get("token")
    user_id = _verify_ws_token(token)
    if not user_id:
        await ws.close(code=4401, reason="Unauthorized")
        return

    await ws.accept()
    logger.info(f"WS connected: user={user_id}")
    last_hash = None
    try:
        while True:
            try:
                digest, events = _current_signals_payload()
                if digest != last_hash:
                    last_hash = digest
                    await ws.send_json({"type": "signals", "count": len(events), "events": events})
                # non-blocking receive for client ping/close with timeout
                try:
                    msg = await asyncio.wait_for(ws.receive_text(), timeout=PUSH_INTERVAL_SECONDS)
                    if msg == "ping":
                        await ws.send_json({"type": "pong"})
                except asyncio.TimeoutError:
                    pass  # interval elapsed, loop to check for changes
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.warning(f"WS loop error: {e}")
                await asyncio.sleep(PUSH_INTERVAL_SECONDS)
    except WebSocketDisconnect:
        logger.info(f"WS disconnected: user={user_id}")
    except Exception as e:
        logger.warning(f"WS terminated: {e}")
