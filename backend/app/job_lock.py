"""Per-job distributed locks. Production requires Redis; dev may use process locks."""
from __future__ import annotations

import logging
import os
import threading
from collections.abc import Callable
from typing import TypeVar

from .settings import settings

logger = logging.getLogger(__name__)
T = TypeVar("T")
LOCK_TTL_SECONDS = 5 * 60
_local_locks: dict[str, threading.Lock] = {}
_local_locks_guard = threading.Lock()


def create_redis_client(required: bool = False):
    url = (settings.redis_url or os.getenv("REDIS_URL", "")).strip()
    if not url or url == "memory://":
        if required:
            raise RuntimeError("REDIS_URL is required for the production scheduler worker")
        return None
    try:
        import redis

        client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=5)
        client.ping()
        return client
    except Exception as exc:
        if required:
            raise RuntimeError("Redis is required and must be reachable by the scheduler worker") from exc
        logger.warning("Redis is unavailable; using a process-local scheduler lock in development: %s", exc)
        return None


def run_with_job_lock(job_name: str, callback: Callable[[], T], redis_client=None) -> T | None:
    """Run callback only while owning a job-specific Redis lock with crash TTL."""
    if redis_client is not None:
        lock = redis_client.lock(
            f"siliconpulse:scheduler:{job_name}",
            timeout=LOCK_TTL_SECONDS,
            blocking_timeout=0,
        )
        if not lock.acquire(blocking=False):
            logger.info("Skipping %s: another scheduler instance owns its lock", job_name)
            return None
        renew_stop = threading.Event()

        def renew_lock():
            while not renew_stop.wait(LOCK_TTL_SECONDS // 3):
                try:
                    if not lock.extend(LOCK_TTL_SECONDS, replace_ttl=True):
                        logger.error("Lost Redis scheduler lock for %s", job_name)
                        return
                except Exception:
                    logger.exception("Could not renew Redis scheduler lock for %s", job_name)
                    return

        renewer = threading.Thread(target=renew_lock, name=f"lock-renew-{job_name}", daemon=True)
        renewer.start()
        try:
            return callback()
        finally:
            renew_stop.set()
            renewer.join(timeout=1)
            try:
                lock.release()
            except Exception:
                logger.warning("Could not release scheduler lock for %s", job_name, exc_info=True)

    with _local_locks_guard:
        lock = _local_locks.setdefault(job_name, threading.Lock())
    if not lock.acquire(blocking=False):
        logger.info("Skipping %s: a local scheduler instance owns its lock", job_name)
        return None
    try:
        return callback()
    finally:
        lock.release()
