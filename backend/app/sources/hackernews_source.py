import json
import requests
from pathlib import Path
from datetime import datetime
from ..settings import settings
from ..utils import deduplicate_and_append, get_current_timestamp
from .. import storage
from ..company_dict import COMPANY_DICT
import logging
import time
logger = logging.getLogger(__name__)

def map_company_from_text(text: str) -> str:
    """
    Simple heuristic to map HN post to known companies.
    Returns company name if found, else "Unknown".
    """
    if not text:
        return "Unknown"
    
    text_lower = text.lower()
    for company, data in COMPANY_DICT.items():
        if company.lower() in text_lower:
            return company
        for alias in data.get("aliases", []):
            if alias.lower() in text_lower:
                return company
    
    return "Unknown"


def classify_event_type(title: str, content: str) -> str:
    """
    Simple heuristic to classify event type based on keywords.
    """
    text = (title + " " + content).lower()
    
    if any(word in text for word in ["acquired", "acquisition", "acqu", "bought"]):
        return "Acquisition"
    elif any(word in text for word in ["partnership", "partner", "collaborate"]):
        return "Contract"
    elif any(word in text for word in ["launched", "launch", "unveiled", "announce"]):
        return "Launch"
    elif any(word in text for word in ["produce", "production", "manufacturing", "fab"]):
        return "Manufacturing"
    elif any(word in text for word in ["ai", "artificial intelligence", "model", "llm", "gpt"]):
        return "AI"
    else:
        return "General"


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
                        
                        title = story.get("title", "")
                        if not title:
                            continue
                        
                        # Get story content
                        # HackerNews via Algolia has limited content; use URL as reference
                        story_url = story.get("url", f"https://news.ycombinator.com/item?id={story_id}")
                        story_text = story.get("story_text", "") or ""
                        
                        # Construct event
                        content = story_text[:500] if story_text else f"From {story.get('author', 'HN')} on HackerNews"
                        
                        event = {
                            "title": title,
                            "content": content,
                            "timestamp": created_at,
                            "source": "HackerNews",
                            "url": story_url,
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
