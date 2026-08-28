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
    Server pushes initial state, then subscribes to Redis Pub/Sub for instant updates.
    Client sends "ping" -> server replies "pong" (keep-alive).
    """
    token = ws.query_params.get("token")
    user_id = _verify_ws_token(token)
    if not user_id:
        await ws.close(code=4401, reason="Unauthorized")
        return

    await ws.accept()
    logger.info(f"WS connected: user={user_id}")
    
    # 1. Send initial state
    digest, events = _current_signals_payload()
    await ws.send_json({"type": "signals", "count": len(events), "events": events})
    
    pubsub = None
    redis_client = None
    try:
        import os
        from .settings import settings
        url = (settings.redis_url or os.getenv("REDIS_URL", "")).strip()
        
        if url and url != "memory://":
            import redis.asyncio as redis_async
            redis_client = redis_async.Redis.from_url(url, decode_responses=True)
            pubsub = redis_client.pubsub()
            await pubsub.subscribe("siliconpulse:signals")
            logger.info("WS subscribed to Redis siliconpulse:signals")
            
        while True:
            try:
                # We need to wait for either a Redis message or a WS message (ping)
                # Since we want to handle pings, we'll use asyncio.wait with FIRST_COMPLETED
                
                ws_task = asyncio.create_task(ws.receive_text())
                
                if pubsub:
                    # Redis get_message is non-blocking with timeout=0, but we can't easily wait on it without loop
                    # Actually, pubsub.get_message(ignore_subscribe_messages=True, timeout=...) blocks.
                    # Let's use a simpler polling approach for Redis or asyncio.sleep
                    redis_task = asyncio.create_task(pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0))
                    
                    done, pending = await asyncio.wait(
                        [ws_task, redis_task],
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    if ws_task in done:
                        msg = ws_task.result()
                        if msg == "ping":
                            await ws.send_json({"type": "pong"})
                        # Need to cancel redis_task since it might be pending
                        redis_task.cancel()
                    else:
                        ws_task.cancel()
                        
                    if redis_task in done and not redis_task.cancelled():
                        message = redis_task.result()
                        if message and message['type'] == 'message':
                            payload = json.loads(message['data'])
                            new_events = payload.get("events", [])
                            if new_events:
                                await ws.send_json({"type": "signals", "count": len(new_events), "events": new_events, "isAppend": True})
                else:
                    # Fallback if no redis (memory only) - wait for ping
                    msg = await asyncio.wait_for(ws_task, timeout=10)
                    if msg == "ping":
                        await ws.send_json({"type": "pong"})
                        
            except asyncio.TimeoutError:
                pass
            except WebSocketDisconnect:
                raise
            except Exception as e:
                logger.warning(f"WS loop error: {e}")
                await asyncio.sleep(2)
                
    except WebSocketDisconnect:
        logger.info(f"WS disconnected: user={user_id}")
    except Exception as e:
        logger.warning(f"WS terminated: {e}")
    finally:
        if pubsub:
            await pubsub.unsubscribe("siliconpulse:signals")
            await pubsub.close()
        if redis_client:
            await redis_client.aclose()
