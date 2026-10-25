"""Scheduled ingestion and delivery job functions.

The functions are deliberately separate from FastAPI lifecycle management;
``app.scheduler_worker`` is the only production scheduler process.
"""
import asyncio
import logging

from .services.news_sources import ingest_news_stream_sync
from .sources.gdelt_source import pull_gdelt_signals
from .sources.hackernews_source import pull_hn_signals

logger = logging.getLogger(__name__)


def pull_all_sources() -> dict:
    """Catch up from primary news sources; event IDs make repeated pulls safe."""
    logger.info("Starting scheduled data pull")
    totals = {}
    for name, pull in (
        ("news", ingest_news_stream_sync),
        ("gdelt", pull_gdelt_signals),
        ("hackernews", pull_hn_signals),
    ):
        try:
            result = pull()
            if isinstance(result, dict):
                result = result.get("new_added", 0)
            totals[name] = int(result or 0)
            logger.info("%s ingestion added %s", name, totals[name])
        except Exception:
            totals[name] = 0
            logger.exception("Scheduled %s ingestion failed", name)
    totals["new_added"] = sum(totals.values())
    return totals


def pull_rss_feeds_sync() -> dict:
    from .sources.rss_source import pull_rss_feeds

    return pull_rss_feeds()


def pull_edgar_sync() -> int:
    from .sources.edgar_source import pull_edgar_signals

    return pull_edgar_signals(days_back=7)


def run_spike_alerts_sync() -> dict:
    from .services.webhook_service import run_spike_alerts_sync as run

    return run()


def run_digest_cron_sync() -> dict:
    from .services.digest_service import run_due_digests_sync

    return run_due_digests_sync()


def pull_sec_filings_sync() -> dict:
    from .services.ingestion_pipeline import ingest_sec_filings

    return asyncio.run(ingest_sec_filings(days_back=7))
