import json
import logging
import time
from datetime import datetime, timedelta, timezone

import requests

from .. import storage
from ..company_dict import COMPANY_DICT
from ..settings import settings
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

def map_company_from_text(text: str) -> str:
    """
    Map article text to known companies using centralized utility.
    Returns company name if found, else "Unknown".
    """
    if not text:
        return "Unknown"

    company = get_primary_company(text)
    return company if company else "Unknown"


def pull_gdelt_signals(max_articles: int = 50) -> int:
    """
    Fetch signals from GDELT API for tech/semiconductor companies.
    GDELT returns global news events indexed by keywords.
    Returns number of new events added.
    """
    events = []

    # Get last checkpoint
    last_checkpoint = storage.get_checkpoint("GDELT")
    now = datetime.now(timezone.utc)
    try:
        start = datetime.fromisoformat((last_checkpoint or "").replace("Z", "+00:00")) - timedelta(hours=24)
        if start.tzinfo is None:
            start = start.replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        start = now - timedelta(hours=settings.ingestion_lookback_hours)
    startdatetime = start.astimezone(timezone.utc).strftime("%Y%m%d%H%M%S")
    enddatetime = now.strftime("%Y%m%d%H%M%S")

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
                url = "https://api.gdeltproject.org/api/v2/doc/doc"
                params = {
                    "query": query,
                    "mode": "json",
                    "maxrecords": min(max_articles, 250),
                    "sort": "date",
                    "sourcelang": "eng",
                    "startdatetime": startdatetime,
                    "enddatetime": enddatetime,
                }

                # Retry logic with exponential backoff (3 attempts, 30s timeout each)
                max_retries = 3
                response = None
                for attempt in range(max_retries):
                    try:
                        response = requests.get(url, params=params, timeout=30)
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

                        raw_title = article.get("title", "")
                        if not raw_title:
                            continue
                        title = sanitize_title(raw_title)
                        raw_content = article.get("pubdate", "") or f"Source: {article.get('sourcecountry', 'Unknown')}"
                        content = sanitize_content(raw_content, max_len=500)
                        url = clean_url(article.get("url", "")) or article.get("url", "")

                        event = {
                            "title": title,
                            "content": content,
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

        # Advance only after a completed pull; overlap windows plus Postgres
        # event-ID conflicts make restart/retry ingestion safe.
        if events:
            newest_ts = max(events, key=lambda x: x.get("timestamp", ""))["timestamp"]
            storage.update_checkpoint("GDELT", newest_ts)
            logger.info(f"{added_count} new GDELT signals added (from {len(events)} fetched)")

        return added_count

    except Exception as e:
        logger.error(f"GDELT fetch failed: {e}")
        return 0
