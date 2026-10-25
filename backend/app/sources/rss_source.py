"""Custom RSS/Atom user feeds (Phase 3.3). Stdlib XML parsing, no new dependency."""
import logging
import time
import xml.etree.ElementTree as ET

from ..settings import settings
from ..services.safe_fetch import safe_fetch_sync
from ..supabase_client import list_enabled_rss_feeds, touch_rss_feed
from ..utils import (
    classify_event_type,
    clean_url,
    deduplicate_and_append,
    get_current_timestamp,
    get_primary_company,
    sanitize_content,
    sanitize_title,
)

logger = logging.getLogger(__name__)

NAMESPACES = {"atom": "http://www.w3.org/2005/Atom", "content": "http://purl.org/rss/1.0/modules/content/"}


def _text(el, names: list[str]) -> str:
    for name in names:
        child = el.find(name, NAMESPACES)
        if child is not None and child.text and child.text.strip():
            return child.text.strip()
    return ""


def parse_feed_xml(xml_text: str) -> list[dict]:
    """Parse RSS 2.0 or Atom XML into [{title, url, content, timestamp}]. Defensive: skips bad items."""
    items: list[dict] = []
    try:
        root = ET.fromstring(xml_text)
    except Exception as e:
        logger.debug(f"RSS XML parse failed: {e}")
        return []
    tag = root.tag.lower()
    if tag.endswith("feed"):  # Atom
        entries = root.findall("atom:entry", NAMESPACES) or root.findall("{http://www.w3.org/2005/Atom}entry")
        for entry in entries[:20]:
            title = _text(entry, ["atom:title"]) or "Untitled"
            link_el = entry.find("atom:link", NAMESPACES)
            url = ""
            if link_el is not None:
                url = link_el.get("href", "") or ""
                if not url:
                    url = _text(entry, ["atom:id"])
            content = _text(entry, ["atom:summary", "atom:content"]) or _text(entry, ["summary", "content"])
            timestamp = _text(entry, ["atom:updated", "atom:published"]) or get_current_timestamp()
            items.append({"title": title, "url": url, "content": content, "timestamp": timestamp})
    else:  # RSS 2.0
        for item in root.findall(".//item")[:20]:
            title = _text(item, ["title"]) or "Untitled"
            url = _text(item, ["link"])
            content = _text(item, ["description", "content:encoded"]) or ""
            timestamp = _text(item, ["pubDate"]) or get_current_timestamp()
            items.append({"title": title, "url": url, "content": content, "timestamp": timestamp})
    return items


def pull_rss_feeds() -> dict:
    """Poll all enabled user feeds (cap 200). Returns {feeds_checked, new_added}."""
    try:
        feeds = list_enabled_rss_feeds()
    except Exception as e:
        logger.warning(f"RSS feed list failed: {e}")
        return {"feeds_checked": 0, "new_added": 0}
    if not feeds:
        return {"feeds_checked": 0, "new_added": 0}

    total_added = 0
    checked = 0
    for feed in feeds:
        feed_id = feed.get("id", "")
        url = feed.get("url", "")
        label = feed.get("label") or "RSS"
        if not url:
            continue
        checked += 1
        try:
            feed_bytes = safe_fetch_sync(url)
            raw_items = parse_feed_xml(feed_bytes.decode("utf-8", errors="replace"))
            events = []
            for it in raw_items:
                title = sanitize_title(it.get("title", ""))
                if not title:
                    continue
                content = sanitize_content(it.get("content", ""), max_len=800) or title
                full_url = clean_url(it.get("url", "")) or it.get("url", "")
                text = f"{title} {content}"
                events.append(
                    {
                        "title": title,
                        "content": content,
                        "timestamp": it.get("timestamp") or get_current_timestamp(),
                        "source": label[:50],
                        "url": full_url,
                        "company": get_primary_company(text) or "Unknown",
                        "event_type": classify_event_type(title, content),
                    }
                )
            added = deduplicate_and_append(events, settings.resolved_data_path)
            total_added += added
            touch_rss_feed(feed_id)
            # Gentle pacing across many feeds
            time.sleep(0.5)
        except Exception as e:
            logger.warning(f"RSS pull failed for {url[:80]}: {e}")
            try:
                touch_rss_feed(feed_id, error=str(e)[:300])
            except Exception:
                pass
    logger.info(f"RSS ingestion: {total_added} new events from {checked} feeds")
    return {"feeds_checked": checked, "new_added": total_added}
