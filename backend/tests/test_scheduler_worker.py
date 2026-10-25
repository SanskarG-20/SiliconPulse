from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


class FakeRedisLock:
    def __init__(self, acquired=True):
        self.acquired = acquired
        self.released = False

    def acquire(self, blocking=False):
        return self.acquired

    def release(self):
        self.released = True

    def extend(self, seconds, replace_ttl=False):
        return True


def test_redis_job_lock_runs_once_and_releases():
    from app.job_lock import run_with_job_lock

    lock = FakeRedisLock()
    redis = MagicMock()
    redis.lock.return_value = lock
    callback = MagicMock(return_value=7)
    assert run_with_job_lock("digest", callback, redis) == 7
    callback.assert_called_once()
    assert lock.released is True
    redis.lock.assert_called_once()


def test_busy_redis_lock_skips_the_job():
    from app.job_lock import run_with_job_lock

    redis = MagicMock()
    redis.lock.return_value = FakeRedisLock(acquired=False)
    callback = MagicMock()
    assert run_with_job_lock("pull_sources", callback, redis) is None
    callback.assert_not_called()


def test_scheduler_jobs_are_immediate_coalesced_and_single_instance():
    from app.scheduler_worker import build_scheduler

    class FakeScheduler:
        def __init__(self, **kwargs):
            self.options = kwargs
            self.jobs = []

        def add_job(self, function, **kwargs):
            self.jobs.append(kwargs)

    start = datetime(2026, 10, 25, 10, 0, tzinfo=timezone.utc)
    scheduler = build_scheduler(MagicMock(), now=start, scheduler_cls=FakeScheduler)
    jobs = {job["id"]: job for job in scheduler.jobs}
    assert set(jobs) == {"pull_sources", "pull_sec", "digest_cron", "spike_alerts", "rss_feeds", "edgar_daily"}
    assert jobs["pull_sources"]["next_run_time"] == start
    assert jobs["digest_cron"]["next_run_time"] > jobs["pull_sources"]["next_run_time"]
    assert all(job["coalesce"] is True and job["max_instances"] == 1 for job in jobs.values())
    assert all(job["misfire_grace_time"] == 24 * 60 * 60 for job in jobs.values())


def test_production_scheduler_requires_redis(monkeypatch):
    from app.job_lock import create_redis_client
    from app.settings import settings

    monkeypatch.setattr(settings, "redis_url", "")
    monkeypatch.delenv("REDIS_URL", raising=False)
    with pytest.raises(RuntimeError, match="REDIS_URL is required"):
        create_redis_client(required=True)


def test_digest_selection_catches_elapsed_hours_but_skips_future_and_already_sent(monkeypatch):
    from app import supabase_client

    rows = [
        {"user_id": "due", "enabled": True, "hour_utc": 9, "email": "a@example.com", "last_sent_at": "2026-10-24T09:00:00Z"},
        {"user_id": "future", "enabled": True, "hour_utc": 13, "email": "b@example.com", "last_sent_at": None},
        {"user_id": "sent", "enabled": True, "hour_utc": 8, "email": "c@example.com", "last_sent_at": "2026-10-25T08:00:00Z"},
        {"user_id": "missed-yesterday", "enabled": True, "hour_utc": 23, "email": "d@example.com", "last_sent_at": "2026-10-24T23:00:00Z"},
    ]
    query = MagicMock()
    query.select.return_value.eq.return_value.execute.return_value = SimpleNamespace(data=rows)
    monkeypatch.setattr(supabase_client, "get_supabase_client", lambda: SimpleNamespace(table=lambda name: query))
    due = supabase_client.list_due_digest_prefs(hour_utc=11)
    assert [item["user_id"] for item in due] == ["due", "missed-yesterday"]


def test_news_ingestion_restarts_from_persisted_checkpoint(monkeypatch):
    import asyncio
    from app.services import news_sources
    from app import storage

    news_sources._cache.clear()
    article = {"title": "Catch-up story", "url": "https://example.test/story", "timestamp": "2026-10-25T10:00:00Z"}
    async def fake_fetch(query, since=None):
        return [article]

    with patch.object(storage, "get_checkpoint", return_value="2026-10-24T12:00:00Z"):
        with patch.object(news_sources, "fetch_all_sources", side_effect=fake_fetch) as fetch:
            with patch.object(news_sources, "deduplicate_and_append", return_value=1):
                with patch.object(storage, "update_checkpoint") as checkpoint:
                    result = asyncio.run(news_sources.ingest_news_stream())
    assert result["new_added"] == 1
    assert fetch.call_count == len(news_sources.SIGNAL_QUERIES)
    assert fetch.call_args.kwargs["since"] == "2026-10-23T12:00:00Z"
    checkpoint.assert_called_once_with("NewsAPI", article["timestamp"])


@pytest.mark.parametrize("delivery, should_mark", [
    ({"email": False, "slack": False}, False),
    ({"email": True, "slack": False}, True),
])
def test_digest_marker_is_written_only_after_a_successful_channel(delivery, should_mark):
    import asyncio
    from app.services import digest_service

    pref = {"user_id": "digest-user", "email": "user@example.com", "webhook_url": ""}
    async def build():
        return {"query": "q", "insight": "{}", "evidence": []}

    async def deliver_result(*args, **kwargs):
        return delivery

    with patch("app.supabase_client.list_due_digest_prefs", return_value=[pref]), \
         patch.object(digest_service, "build_digest", side_effect=build), \
         patch.object(digest_service, "deliver_to_user", side_effect=deliver_result), \
         patch("app.supabase_client.mark_digest_sent") as mark:
        result = asyncio.run(digest_service._run_due_digests())
        assert result["sent"] == int(should_mark)
        assert mark.called is should_mark
