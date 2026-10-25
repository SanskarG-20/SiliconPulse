from __future__ import annotations

import logging
import os

from slowapi import Limiter
from slowapi.util import get_remote_address

from ..settings import settings

logger = logging.getLogger(__name__)

def resolve_storage_uri(app_env: str, redis_url: str | None) -> str:
    """Use process-local storage in development and require Redis in production."""
    url = (redis_url or os.getenv("REDIS_URL", "")).strip()
    if app_env.lower() == "production" and (not url or url == "memory://"):
        raise RuntimeError("REDIS_URL is required for production rate limiting")
    return url or "memory://"


def validate_rate_limit_store() -> None:
    """Ping the configured Redis before the production API begins serving."""
    if settings.app_env.lower() != "production":
        return
    if _storage == "memory://":
        raise RuntimeError("Production rate limiting cannot use memory:// storage")
    from ..job_lock import create_redis_client
    try:
        create_redis_client(required=True)
    except Exception as exc:
        raise RuntimeError("Production rate limiting requires reachable Redis") from exc


# Example: REDIS_URL=redis://default:password@host:6379/0
_storage = resolve_storage_uri(settings.app_env, settings.redis_url)
if _storage != "memory://":
    logger.info(f"Rate limiter using Redis: {_storage.split('@')[-1]}")
else:
    logger.debug("Rate limiter using memory:// (single-instance)")

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"], storage_uri=_storage)
