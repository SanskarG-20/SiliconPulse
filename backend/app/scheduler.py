import logging
import threading

from .services.news_sources import ingest_news_stream_sync
from .sources.gdelt_source import pull_gdelt_signals
from .sources.hackernews_source import pull_hn_signals

logger = logging.getLogger(__name__)

try:
    from apscheduler.schedulers.background import BackgroundScheduler
except ImportError:
    BackgroundScheduler = None

scheduler = BackgroundScheduler() if BackgroundScheduler else None
_fallback_stop = threading.Event()
_fallback_thread = None

def pull_all_sources():
    """Pull data from all sources (News APIs + GDELT + HackerNews)"""
    try:
        logger.info("Starting scheduled data pull...")

        # Pull from unified news sources (aggregates all 4 APIs)
        news_result = ingest_news_stream_sync()
        logger.info(f"News APIs: {news_result}")
        news_added = 0
        if isinstance(news_result, dict):
            news_added_value = news_result.get("new_added")
            news_added = news_added_value if isinstance(news_added_value, int) else 0

        # Pull from GDELT
        gdelt_count = pull_gdelt_signals() or 0
        logger.info(f"Pulled {gdelt_count} events from GDELT")

        # Pull from HackerNews
        hn_count = pull_hn_signals() or 0
        logger.info(f"Pulled {hn_count} events from HackerNews")

        total = news_added + gdelt_count + hn_count
        logger.info(f"Total: {total} new events added to stream")

    except Exception as e:
        logger.error(f"Error during scheduled pull: {e}", exc_info=True)


def pull_sec_filings_sync():
    """Sync wrapper for SEC 8-K ingestion (best-effort, async)."""
    try:
        import asyncio

        from app.services.ingestion_pipeline import ingest_sec_filings

        logger.info("Starting SEC 8-K ingestion...")
        try:
            result = asyncio.run(ingest_sec_filings(days_back=3))
        except RuntimeError:
            loop = asyncio.new_event_loop()
            try:
                result = loop.run_until_complete(ingest_sec_filings(days_back=3))
            finally:
                loop.close()
        logger.info(f"SEC ingestion result: {result}")
    except Exception as e:
        logger.warning(f"SEC ingestion skipped/failed: {e}")

def start_scheduler():
    """Start the background scheduler"""
    # Run first pull in background thread so it doesn't block app startup
    def initial_pull():
        try:
            pull_all_sources()
        except Exception as e:
            logger.error(f"Initial data pull failed: {e}", exc_info=True)

    # Start initial pull in background thread
    initial_thread = threading.Thread(target=initial_pull, daemon=True)
    initial_thread.start()

    if scheduler is None:
        logger.warning("APScheduler is not installed; using lightweight fallback scheduler.")

        def fallback_loop():
            sec_counter = 0
            while not _fallback_stop.wait(300):
                pull_all_sources()
                sec_counter += 1
                if sec_counter >= 72:  # 72 * 5min = 6h
                    pull_sec_filings_sync()
                    sec_counter = 0

        global _fallback_thread
        _fallback_thread = threading.Thread(target=fallback_loop, daemon=True)
        _fallback_thread.start()
        return

    # Schedule pulls every 5 minutes
    if not scheduler.get_job('pull_sources'):
        scheduler.add_job(pull_all_sources, 'interval', minutes=5, id='pull_sources')
    # SEC 8-K ingestion every 6 hours (less frequent, heavier)
    if not scheduler.get_job('pull_sec'):
        scheduler.add_job(pull_sec_filings_sync, 'interval', hours=6, id='pull_sec')
    if not scheduler.running:
        scheduler.start()
    logger.info("Background scheduler started - pulling data every 5 min (news) + 6h (SEC) (first pull running in background)")

def stop_scheduler():
    """Stop the background scheduler"""
    if scheduler is None:
        _fallback_stop.set()
        logger.info("Fallback scheduler stopped")
        return

    if scheduler.running:
        scheduler.shutdown()
        logger.info("Background scheduler stopped")
