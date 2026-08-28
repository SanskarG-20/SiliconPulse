"""
Tests for distributed ingestion (1M+ events/day target).
Covers sharding, queue depth, worker pool, and metrics.
"""
from unittest.mock import patch, MagicMock
import time


def test_queue_sharding_and_depth():
    from app.workers.queue import DistributedQueue

    q = DistributedQueue(shard_count=4)
    events = [
        {"title": f"Event {i}", "content": f"content {i}", "source": "Test", "timestamp": "2026-08-20T12:00:00Z"}
        for i in range(10)
    ]
    n = q.push(events)
    assert n == 10
    depth = q.depth()
    assert depth["shards"] == 4
    assert depth["backend"] in ("memory", "redis")
    # Pop from each shard should eventually drain all 10
    total = 0
    for shard in range(4):
        batch = q.pop_batch(shard, max_batch=50, timeout=0.1)
        total += len(batch)
    assert total == 10


def test_queue_shard_determinism():
    from app.workers.queue import _shard_for

    ev = {"title": "TSMC N2 yield", "content": "yield", "source": "Reuters", "url": "https://a.com"}
    s1 = _shard_for(ev, 4)
    s2 = _shard_for(ev, 4)
    assert s1 == s2
    assert 0 <= s1 < 4


def test_worker_pool_processes_batch():
    from app.workers.distributed import WorkerPool

    pool = WorkerPool(worker_count=2, batch_size=10, poll_interval=0.1)
    # Don't start threads; test _process_batch directly via push + manual pop
    events = [
        {"title": f"Worker Test {i}", "content": f"content {i}", "source": "Test", "timestamp": "2026-08-20T12:00:00Z", "url": f"https://t.com/{i}"}
        for i in range(5)
    ]
    # Mock deduplicate_and_append to avoid file I/O
    with patch("app.utils.deduplicate_and_append", return_value=5) as mock_dedup:
        with patch("app.workers.distributed._redis_sadd_if_new", return_value=True):
            from app.workers.distributed import _process_batch

            added = _process_batch(events)
            assert added == 5
            mock_dedup.assert_called_once()


def test_worker_pool_push_and_stats():
    from app.workers.distributed import WorkerPool

    pool = WorkerPool(worker_count=2, batch_size=5, poll_interval=0.05)
    pool.start()
    try:
        events = [
            {"title": f"Stats Test {i}", "content": "x", "source": "Test", "timestamp": "2026-08-20T12:00:00Z", "url": f"https://s.com/{i}"}
            for i in range(4)
        ]
        with patch("app.workers.distributed._process_batch", return_value=2):
            pool.push(events)
            time.sleep(0.3)  # let workers drain
            stats = pool.stats()
            assert stats["workers"] == 2
            # Processed should be >=0 (workers may have run)
            assert "processed" in stats
    finally:
        pool.stop()


def test_metrics_includes_workers():
    from fastapi.testclient import TestClient
    from app.core.auth import get_current_user
    from app.main import app

    # Ensure metrics endpoint includes worker stats
    client = TestClient(app)
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "workers" in data
    assert "queue" in data
    assert "vector_signals" in data


def test_pathway_sharding():
    from app.workers.pathway_distributed import _shard_for

    # Same event_id should map to same shard
    assert _shard_for("abc123", 4) == _shard_for("abc123", 4)
    # Different shards in range
    for count in [1, 2, 4, 8]:
        s = _shard_for("test-id", count)
        assert 0 <= s < count
