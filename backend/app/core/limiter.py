import os
import logging

from slowapi import Limiter
from slowapi.util import get_remote_address

logger = logging.getLogger(__name__)

# Use Redis when REDIS_URL is set (required for horizontal scale), else in-memory.
# Example: REDIS_URL=redis://default:password@host:6379/0  (also via settings.redis_url)
_storage = os.getenv("REDIS_URL", "").strip() or "memory://"
if _storage != "memory://":
    logger.info(f"Rate limiter using Redis: {_storage.split('@')[-1]}")
else:
    logger.debug("Rate limiter using memory:// (single-instance)")

limiter = Limiter(key_func=get_remote_address, default_limits=["100/minute"], storage_uri=_storage)
