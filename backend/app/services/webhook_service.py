"""Team webhook spike alerts (Phase 2.4). Best-effort, never raises."""
from __future__ import annotations

import logging
import math
from collections import Counter
from datetime import datetime, timedelta
from urllib.parse import urlsplit

from app.services.digest_service import send_slack
from app.settings import settings
from app.utils import parse_timestamp, safe_read_jsonl

logger = logging.getLogger(__name__)

ALLOWED_EVENTS = {"spike.alert", "digest"}


def validate_webhook_url(url: str) -> str:
    """Allow only Slack/Discord incoming webhooks. Returns cleaned URL or ''."""
    url = (url or "").strip()
    try:
        parts = urlsplit(url)
        if (
            parts.scheme == "https"
            and parts.username is None
            and parts.password is None
            and parts.port in (None, 443)
            and (
                (parts.hostname == "hooks.slack.com" and parts.path.startswith("/services/"))
                or (parts.hostname == "discord.com" and parts.path.startswith("/api/webhooks/"))
            )
        ):
            return url[:500]
    except ValueError:
        pass
    return ""


def global_spike(days: int = 7) -> dict:
    """Detect whether today is a spike day on the global stream."""
    try:
        events = safe_read_jsonl(settings.resolved_data_path, limit=max(500, days * 100), freshness_hours=None)
    except Exception:
        events = []
    now = datetime.utcnow()
    start = now - timedelta(days=days)
    daily: Counter = Counter()
    top: Counter = Counter()
    for ev in events:
        try:
            ts = parse_timestamp(ev.get("timestamp", ""))
        except Exception:
            continue
        if ts < start:
            continue
        daily[ts.date().isoformat()] += 1
        top[str(ev.get("company") or "Unknown")] += 1
    series = []
    cursor = start.date()
    while cursor <= now.date():
        series.append(daily.get(cursor.isoformat(), 0))
        cursor += timedelta(days=1)
    mean = sum(series) / len(series) if series else 0
    var = sum((c - mean) ** 2 for c in series) / len(series) if series else 0
    std = math.sqrt(var)
    today_count = series[-1] if series else 0
    is_spike = bool(std > 0 and today_count >= 3 and today_count > mean + 2 * std)
    return {
        "is_spike": is_spike,
        "today": today_count,
        "mean": round(mean, 2),
        "std": round(std, 2),
        "top_companies": [{"company": k, "count": v} for k, v in top.most_common(3)],
        "date": now.date().isoformat(),
    }


def run_spike_alerts_sync() -> dict:
    import asyncio

    try:
        return asyncio.run(_run_spike_alerts())
    except RuntimeError:
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(_run_spike_alerts())
        finally:
            loop.close()


async def _run_spike_alerts() -> dict:
    from app.supabase_client import list_enabled_spike_webhooks, mark_webhook_sent

    try:
        webhooks = list_enabled_spike_webhooks()
    except Exception as e:
        logger.warning(f"spike alerts prefs fetch failed: {e}")
        return {"checked": 0, "sent": 0, "spike": False}
    if not webhooks:
        return {"checked": 0, "sent": 0, "spike": False}
    spike = global_spike()
    if not spike["is_spike"]:
        return {"checked": len(webhooks), "sent": 0, "spike": False}
    top = ", ".join(f"{c['company']} ({c['count']})" for c in spike["top_companies"]) or "stream"
    text = f"Signal spike: {spike['today']} signals today (avg {spike['mean']}/day). Hot: {top}."
    sent = 0
    for wh in webhooks:
        try:
            if await send_slack(wh.get("url", ""), text):
                sent += 1
            mark_webhook_sent(wh.get("id", ""))
        except Exception as e:
            logger.warning(f"spike alert send failed: {e}")
    logger.info(f"Spike alerts: {sent}/{len(webhooks)} sent for {spike['date']}")
    return {"checked": len(webhooks), "sent": sent, "spike": True, "today": spike["today"]}
