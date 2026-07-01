import json
import requests
from pathlib import Path
from datetime import datetime, timedelta
from ..settings import settings
from ..utils import deduplicate_and_append, get_current_timestamp
from .. import storage
from ..company_dict import COMPANY_DICT
import logging
import time

logger = logging.getLogger(__name__)

def map_company_from_text(text: str) -> str:
    """
    Simple heuristic to map article text to known companies.
    Returns company name if found, else "Unknown".
    """
    if not text:
        return "Unknown"
    
    text_lower = text.lower()
    for company, data in COMPANY_DICT.items():
        # Check company name and aliases
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
    
    if any(word in text for word in ["acquired", "acquisition", "acqu", "bought", "deal"]):
        return "Acquisition"
    elif any(word in text for word in ["partnership", "partner", "collaborate", "joint", "agreement"]):
        return "Contract"
    elif any(word in text for word in ["launched", "launch", "unveiled", "announce", "release", "open-source"]):
        return "Launch"
    elif any(word in text for word in ["produce", "production", "manufacturing", "fab", "yield", "fabrication"]):
        return "Manufacturing"
    elif any(word in text for word in ["supply", "supply chain", "shortage", "capacity"]):
        return "Supply Chain"
    elif any(word in text for word in ["ai", "artificial intelligence", "model", "gpt", "llama"]):
        return "AI"
    else:
        return "General"


def pull_gdelt_signals(max_articles: int = 50) -> int:
    """
    Fetch signals from GDELT API for tech/semiconductor companies.
    GDELT returns global news events indexed by keywords.
    Returns number of new events added.
    """
    events = []
    
    # Get last checkpoint
    last_checkpoint = storage.get_checkpoint("GDELT")
    
    try:
        # GDELT 2.0 API: Search for recent articles mentioning our companies
        # Using the SearchNewsByKeyword endpoint
        companies_to_search = list(COMPANY_DICT.keys())[:10]  # Limit to avoid too many requests
        
        for company in companies_to_search:
            try:
                # Query GDELT API for articles mentioning this company
                # Using the V2 DocByDate API for recent articles
                query = f'"{company}" OR "{company.lower()}"'
                
                # GDELT format: max recent articles about each company
                url = f"https://api.gdeltproject.org/api/v2/doc/doc?query={query}&mode=json&maxrecords=10&sort=date&sourcelang=eng"
                
                # Retry logic with exponential backoff (3 attempts, 30s timeout each)
                max_retries = 3
                response = None
                for attempt in range(max_retries):
                    try:
                        response = requests.get(url, timeout=30)
                        response.raise_for_status()
                        break  # Success, exit retry loop
                    except requests.exceptions.HTTPError as e:
                        if response is not None and response.status_code == 429:
                            logger.warning(f"GDELT rate limit (429) hit for {company}. Backing off.")
                            time.sleep(5)  # Backoff if rate limited
                            response = None
                            break # Break retry loop on 429
                        elif attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 2
                            logger.warning(f"GDELT HTTP error for {company} (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            logger.warning(f"GDELT HTTP error for {company}: {e}")
                            response = None
                    except requests.Timeout:
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                            logger.warning(f"GDELT timeout for {company} (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            logger.warning(f"GDELT API request failed for {company}: Connection timeout after {max_retries} attempts")
                            response = None
                    except requests.ConnectionError as e:
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 2
                            logger.warning(f"GDELT connection error for {company} (attempt {attempt+1}/{max_retries}), retrying in {wait_time}s...")
                            time.sleep(wait_time)
                        else:
                            logger.warning(f"GDELT connection error for {company}: {e}")
                            response = None
                
                if response is None:
                    continue
                
                try:
                    data = response.json()
                except json.JSONDecodeError as e:
                    logger.warning(f"GDELT JSON decoding error for {company}: {e}. Response: {response.text[:100]}")
                    continue
                articles = data.get("articles", [])
                
                for article in articles:
                    try:
                        # Parse GDELT article format
                        event_date = article.get("sedate", "")
                        if not event_date:
                            continue
                        
                        # Convert YYYYMMDD to ISO
                        if len(event_date) == 8:
                            timestamp = f"{event_date[:4]}-{event_date[4:6]}-{event_date[6:8]}T12:00:00Z"
                        else:
                            timestamp = get_current_timestamp()
                        
                        # Checkpoint filtering
                        if last_checkpoint and timestamp <= last_checkpoint:
                            continue
                        
                        title = article.get("title", "")
                        content = article.get("pubdate", "")  # GDELT returns limited content
                        url = article.get("url", "")
                        
                        if not title:
                            continue
                        
                        event = {
                            "title": title,
                            "content": content or f"Source: {article.get('sourcecountry', 'Unknown')}",
                            "timestamp": timestamp,
                            "source": "GDELT",
                            "url": url,
                            "company": map_company_from_text(title + " " + content),
                            "event_type": classify_event_type(title, content)
                        }
                        
                        events.append(event)
                    except Exception as e:
                        logger.warning(f"Error parsing GDELT article for {company}: {e}")
                        continue
                        
            except requests.RequestException as e:
                logger.warning(f"GDELT API request failed for {company}: {e}")
                continue
            except Exception as e:
                logger.warning(f"Error fetching GDELT signals for {company}: {e}")
                continue
            finally:
                # Add delay between company requests to avoid GDELT rate limits
                time.sleep(1.5)
        
        # Write to stream
        added_count = deduplicate_and_append(events, settings.resolved_data_path)
        
        # Update checkpoint if we added new events
        if events:
            newest_ts = max(events, key=lambda x: x.get("timestamp", ""))["timestamp"]
            storage.update_checkpoint("GDELT", newest_ts)
            logger.info(f"{added_count} new GDELT signals added (from {len(events)} fetched)")
        
        return added_count
        
    except Exception as e:
        logger.error(f"GDELT fetch failed: {e}")
        return 0
