import logging
import time

import requests

from .. import storage
from ..settings import settings
from ..utils import (
    classify_event_type,
    clean_url,
    deduplicate_and_append,
    extract_primary_url,
    get_current_timestamp,
    get_primary_company,
    sanitize_content,
    sanitize_title,
)

logger = logging.getLogger(__name__)

def map_company_from_text(text: str) -> str:
    """
    Map HN post to known companies using centralized utility.
    Returns company name if found, else "Unknown".
    """
    if not text:
        return "Unknown"

    company = get_primary_company(text)
    return company if company else "Unknown"


def pull_hn_signals(max_stories: int = 100) -> int:
    """
    Fetch signals from HackerNews using Algolia API.
    Filters for tech/semiconductor relevant stories.
    Returns number of new events added.
    """
    events = []

    # Get last checkpoint
    last_checkpoint = storage.get_checkpoint("HackerNews")

    try:
        # Use Algolia HN API - faster and better filtering than official API
        # Search for relevant keywords
        keywords = ["AI", "semiconductor", "chip", "GPU", "NVIDIA", "TSMC", "Intel", "Apple", "Google", "Meta", "Amazon"]

        for keyword in keywords:
            try:
                # Algolia HN API search endpoint
                url = f"https://hn.algolia.com/api/v1/search?query={keyword}&tags=story&hitsPerPage=20&typoTolerance=false"

                # Retry logic with exponential backoff (2 attempts, 15s timeout)
                max_retries = 2
                response = None
                for attempt in range(max_retries):
                    try:
                        response = requests.get(url, timeout=15)
                        response.raise_for_status()
                        break  # Success, exit retry loop
                    except requests.Timeout:
                        if attempt < max_retries - 1:
                            wait_time = 3
                            logger.warning(f"HackerNews timeout for '{keyword}' (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            logger.warning(f"HackerNews timeout for '{keyword}': Connection timeout after {max_retries} attempts")
                            continue  # Skip to next keyword
                    except requests.ConnectionError as e:
                        if attempt < max_retries - 1:
                            wait_time = 3
                            logger.warning(f"HackerNews connection error for '{keyword}' (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            logger.warning(f"HackerNews connection error for '{keyword}': {e}")
                            continue  # Skip to next keyword

                if response is None:
                    continue

                data = response.json()
                hits = data.get("hits", [])

                for story in hits:
                    try:
                        # Skip if already processed
                        story_id = story.get("objectID", "")
                        created_at = story.get("created_at", "")

                        if not created_at:
                            created_at = get_current_timestamp()

                        # Checkpoint filtering
                        if last_checkpoint and created_at <= last_checkpoint:
                            continue

                        raw_title = story.get("title", "")
                        if not raw_title:
                            continue
                        title = sanitize_title(raw_title)

                        # Get story content — Algolia story_text is HTML-escaped with tracking URLs
                        story_url = story.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                        story_url = clean_url(story_url) or story_url
                        # Extract primary URL: prefer story_url, fallback to first href in story_text
                        raw_story_text = story.get("story_text", "") or ""
                        story_text = sanitize_content(raw_story_text, max_len=500)
                        if not story_text:
                            story_text = f"From {story.get('author', 'HN')} on HackerNews"
                        # If sanitized text is still empty (e.g., only URLs), keep at least the URL host
                        content = story_text

                        # Use cleaned URL for View source — ensure it is the story's canonical URL without tracking
                        url = extract_primary_url(raw_story_text, story_url) or story_url
                        url = clean_url(url) or story_url

                        event = {
                            "title": title,
                            "content": content,
                            "timestamp": created_at,
                            "source": "HackerNews",
                            "url": url,
                            "company": map_company_from_text(title + " " + content),
                            "event_type": classify_event_type(title, content)
                        }

                        events.append(event)

                    except Exception as e:
                        logger.warning(f"Error parsing HN story: {e}")
                        continue

            except requests.RequestException as e:
                logger.warning(f"HN API request failed for keyword '{keyword}': {e}")
                continue
            except Exception as e:
                logger.warning(f"Error fetching HN signals for keyword '{keyword}': {e}")
                continue

        # Write to stream
        added_count = deduplicate_and_append(events, settings.resolved_data_path)

        # Update checkpoint if we added new events
        if events:
            newest_ts = max(events, key=lambda x: x.get("timestamp", ""))["timestamp"]
            storage.update_checkpoint("HackerNews", newest_ts)
            logger.info(f"{added_count} new HackerNews signals added (from {len(events)} fetched)")

        return added_count

    except Exception as e:
        logger.error(f"HackerNews fetch failed: {e}")
        return 0
