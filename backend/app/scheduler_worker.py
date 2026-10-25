"""Dedicated APScheduler entrypoint: ``python -m app.scheduler_worker``."""
from __future__ import annotations

import logging
import signal
from datetime import datetime, timedelta, timezone
from functools import partial

from .job_lock import create_redis_client, run_with_job_lock
from .scheduler import (
    pull_all_sources,
    pull_edgar_sync,
    pull_rss_feeds_sync,
    pull_sec_filings_sync,
    run_digest_cron_sync,
    run_spike_alerts_sync,
)
from .settings import settings
from .supabase_client import is_supabase_enabled

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


def _locked(redis_client, job_name: str, callback):
    return run_with_job_lock(job_name, callback, redis_client)


def build_scheduler(redis_client=None, now: datetime | None = None, scheduler_cls=None):
    """Build jobs with immediate first runs so downtime is caught up at startup."""
    if scheduler_cls is None:
        from apscheduler.schedulers.blocking import BlockingScheduler

        scheduler_cls = BlockingScheduler
    scheduler = scheduler_cls(timezone=timezone.utc)
    start_at = now or datetime.now(timezone.utc)
    jobs = [
        ("pull_sources", pull_all_sources, {"minutes": 5}, 0),
        ("pull_sec", pull_sec_filings_sync, {"hours": 6}, 10),
        ("digest_cron", run_digest_cron_sync, {"hours": 1}, 20),
        ("spike_alerts", run_spike_alerts_sync, {"hours": 1}, 30),
        ("rss_feeds", pull_rss_feeds_sync, {"hours": 1}, 40),
        ("edgar_daily", pull_edgar_sync, {"hours": 24}, 50),
    ]
    for job_id, callback, interval, offset in jobs:
        scheduler.add_job(
            partial(_locked, redis_client, job_id, callback),
            trigger="interval",
            id=job_id,
            next_run_time=start_at + timedelta(seconds=offset),
            coalesce=True,
            max_instances=1,
            misfire_grace_time=24 * 60 * 60,
            **interval,
        )
    return scheduler


def main() -> None:
    production = settings.app_env.strip().lower() == "production"
    if production and not is_supabase_enabled():
        raise RuntimeError("APP_ENV=production requires Supabase/Postgres")
    if is_supabase_enabled():
        from .services.signal_store import check_ready

        check_ready()
    redis_client = create_redis_client(required=production)
    scheduler = build_scheduler(redis_client)
    logger.info("Starting dedicated scheduler worker (environment=%s)", settings.app_env)

    def stop_on_sigterm(signum, frame):
        raise SystemExit(0)

    signal.signal(signal.SIGTERM, stop_on_sigterm)
    try:
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logger.info("Stopping scheduler worker")
    finally:
        if scheduler.running:
            scheduler.shutdown(wait=True)
        if redis_client is not None:
            redis_client.close()


if __name__ == "__main__":
    main()
