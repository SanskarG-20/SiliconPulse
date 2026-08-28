"""
Distributed ingestion worker pool for 1M+ events/day.

- Shard-aware: events hashed to worker by event_id % worker_count
- Batching: each worker drains up to batch_size per tick
- Dedup: Redis SETNX fast-path + SQLite fallback (storage.is_duplicate)
- Vector: per-worker batched embeddings
- Backpressure: queue depth exposed via /metrics, workers self-throttle
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Any

from app.settings import settings
from app.workers.queue import DistributedQueue

logger = logging.getLogger(__name__)

# Metrics (exposed via app.main metrics)
_worker_stats = {
    "processed": 0,
    "batches": 0,
    "errors": 0,
    "queue_depth": 0,
    "workers": 0,
}
_stats_lock = threading.Lock()

# File append lock (JSONL is not concurrent-safe)
_file_lock = threading.Lock()

# Optional Redis dedup SET
_REDIS_DEDUP_KEY = "siliconpulse:dedup"


def _redis_sadd_if_new(event_id: str) -> bool | None:
    """Return True if newly added, False if already exists, None if Redis unavailable."""
    try:
        import os

        url = (settings.redis_url or os.getenv("REDIS_URL", "")).strip()
        if not url or url == "memory://":
            return None
        import redis  # type: ignore

        client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=1)
        # SADD returns 1 if added, 0 if exists
        added = client.sadd(_REDIS_DEDUP_KEY, event_id)  # type: ignore
        # Expire dedup set after freshness window (12h) to avoid unbounded growth
        try:
            client.expire(_REDIS_DEDUP_KEY, settings.freshness_hours * 3600 + 3600)  # type: ignore
        except Exception:
            pass
        return bool(added)
    except Exception as e:
        logger.debug(f"Redis dedup unavailable: {e}")
        return None


def _process_batch(events: list[dict]) -> int:
    if not events:
        return 0

    # Tag phase (company/event_type) - same as pathway pipeline
    try:
        from app.utils import deduplicate_and_append

        # deduplicate_and_append already handles SQLite dedup + file append + vector enqueue
        # We add Redis fast-path before calling it to reduce SQLite contention
        filtered: list[dict] = []
        for ev in events:
            try:
                from app.utils import compute_event_id

                eid = compute_event_id(ev)
                redis_new = _redis_sadd_if_new(eid)
                if redis_new is False:
                    continue  # duplicate in Redis
                # If Redis says new or unavailable, fall through to SQLite check inside deduplicate_and_append
                filtered.append(ev)
            except Exception:
                filtered.append(ev)

        if not filtered:
            return 0

        # Serialize file appends under lock to avoid JSONL interleaving
        with _file_lock:
            added = deduplicate_and_append(filtered, settings.resolved_data_path)
        return added
    except Exception as e:
        logger.warning(f"Batch process failed: {e}")
        with _stats_lock:
            _worker_stats["errors"] += 1
        return 0


class WorkerPool:
    def __init__(self, worker_count: int | None = None, batch_size: int = 50, poll_interval: float = 0.4):
        self.worker_count = worker_count or int(getattr(settings, "worker_count", 4) or 4)
        self.worker_count = max(1, min(self.worker_count, 16))
        self.batch_size = batch_size
        self.poll_interval = poll_interval
        self._queue = DistributedQueue(shard_count=self.worker_count)
        self._threads: list[threading.Thread] = []
        self._stop = threading.Event()
        self._started = False

    def start(self):
        if self._started:
            return
        self._started = True
        with _stats_lock:
            _worker_stats["workers"] = self.worker_count
        for shard_id in range(self.worker_count):
            t = threading.Thread(target=self._worker_loop, args=(shard_id,), daemon=True, name=f"ingest-worker-{shard_id}")
            t.start()
            self._threads.append(t)
        logger.info(f"Distributed WorkerPool started: {self.worker_count} workers, batch={self.batch_size}")

    def stop(self):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2)
        self._threads.clear()
        self._started = False
        logger.info("WorkerPool stopped")

    def push(self, events: list[dict]) -> int:
        return self._queue.push(events)

    def depth(self):
        return self._queue.depth()

    def stats(self):
        with _stats_lock:
            return dict(_worker_stats)

    def _worker_loop(self, shard_id: int):
        logger.debug(f"Worker {shard_id} started")
        while not self._stop.is_set():
            try:
                batch = self._queue.pop_batch(shard_id, max_batch=self.batch_size, timeout=self.poll_interval)
                if batch:
                    added = _process_batch(batch)
                    with _stats_lock:
                        _worker_stats["processed"] += len(batch)
                        _worker_stats["batches"] += 1
                        if added:
                            _worker_stats["queue_depth"] = max(0, _worker_stats.get("queue_depth", 0) - added)
                    if added:
                        logger.debug(f"Worker {shard_id}: batch {len(batch)} -> added {added}")
                else:
                    # idle backoff
                    time.sleep(self.poll_interval)
            except Exception as e:
                logger.warning(f"Worker {shard_id} error: {e}")
                with _stats_lock:
                    _worker_stats["errors"] += 1
                time.sleep(1)


# Global singleton (imported by scheduler and routes)
_pool: WorkerPool | None = None
_pool_lock = threading.Lock()


def get_pool() -> WorkerPool:
    global _pool
    with _pool_lock:
        if _pool is None:
            # Allow env override
            import os

            wc = int(os.getenv("WORKER_COUNT", "") or getattr(settings, "worker_count", 0) or 4)
            _pool = WorkerPool(worker_count=wc)
        return _pool


def start_distributed_workers():
    """Called from lifespan startup when enabled."""
    # Enable via settings.use_distributed_workers or env WORKER_COUNT>1
    enabled = bool(getattr(settings, "use_distributed_workers", False)) or int(getattr(settings, "worker_count", 0) or 0) > 1
    # Also auto-enable when REDIS_URL is set (implies horizontal scale intent)
    import os

    if os.getenv("REDIS_URL") or (settings.redis_url or "").strip():
        enabled = True
    if not enabled:
        logger.debug("Distributed workers disabled (single-instance mode)")
        return
    pool = get_pool()
    pool.start()


def stop_distributed_workers():
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.stop()
            except Exception:
                pass
            _pool = None


if __name__ == "__main__":
    import argparse
    import os

    parser = argparse.ArgumentParser(description="SiliconPulse distributed worker")
    parser.add_argument("--workers", type=int, default=int(os.getenv("WORKER_COUNT", "4")))
    parser.add_argument("--batch", type=int, default=50)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
    pool = WorkerPool(worker_count=args.workers, batch_size=args.batch)
    pool.start()
    print(f"Worker pool running ({args.workers} workers). Press Ctrl+C to stop.")
    try:
        while True:
            time.sleep(5)
            print(f"Stats: {pool.stats()} Depth: {pool.depth()}")
    except KeyboardInterrupt:
        pool.stop()
        print("Stopped")
