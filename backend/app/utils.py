"""
Utility functions for SiliconPulse backend
"""
from __future__ import annotations

import hashlib
import html as html_lib
import json
import logging
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Import storage module (circular import avoidance handled by function calls)
# We'll import inside functions where needed or rely on caller to pass dependencies if strict separation required
# But for this app structure, direct import is fine as storage doesn't import utils
from . import storage
from .company_dict import COMPANY_DICT

logger = logging.getLogger(__name__)

# Compile regex once at module load
_COMPANY_PATTERN = re.compile(r'\b[A-Z][a-zA-Z0-9]+(?: [&-] [A-Z][a-zA-Z0-9]+)*\b')
_STOPWORDS = {"The", "A", "An", "In", "On", "At", "To", "From", "By", "With", "As", "It", "This", "That", "For", "But", "And", "Or", "If", "When"}
# Known acronyms that look like companies but aren't
_KNOWN_ACRONYMS = {"GPU", "CPU", "AI", "API", "SDK", "UI", "UX", "IoT", "ML", "LLM", "GPT", "TPU", "NPU", "VPU", "FPGA", "ASIC", "SoC", "RAM", "SSD", "HDD", "USB", "PCIe", "DDR", "HBM", "EUV", "CoWoS", "TSMC", "SKU", "IPO", "CEO", "CTO", "CFO"}

# Build alias-to-canonical mapping from COMPANY_DICT for fast lookup
# Sort aliases by length (longest first) to match multi-word aliases before single words
_COMPANY_ALIAS_MAP: dict[str, str] = {}
_alias_entries = []
for canonical, data in COMPANY_DICT.items():
    _alias_entries.append((canonical.lower(), canonical))
    for alias in data.get("aliases", []):
        _alias_entries.append((alias.lower(), canonical))

# Sort by alias length descending so "jensen huang" matches before "jensen"
_alias_entries.sort(key=lambda x: len(x[0]), reverse=True)
for alias_lower, canonical in _alias_entries:
    if alias_lower not in _COMPANY_ALIAS_MAP:
        _COMPANY_ALIAS_MAP[alias_lower] = canonical

# ---------------------------------------------------------------------------
# HTML sanitization & URL cleaning (fix raw <a href> + &#x2F; + utm_ tracking)
# ---------------------------------------------------------------------------

_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "utm_id", "utm_name", "utm_reader", "utm_viz_id", "fbclid", "gclid",
    "igshid", "mc_eid", "mkt_tok", "_hsenc", "_hsmi",
}

# Regex to find URLs even inside truncated hrefs
_URL_RE = re.compile(r"https?://[^\s\"'<>]+", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]*>")
_WS_RE = re.compile(r"\s+")

def _decode_entities(text: str) -> str:
    """Double-decode to handle &#x2F; and &amp; chains."""
    if not text:
        return ""
    # html.unescape handles &#x2F;, &#47;, &amp; etc. Do twice for double-encoded
    prev = None
    cur = text
    for _ in range(3):
        if cur == prev:
            break
        prev = cur
        cur = html_lib.unescape(cur)
    return cur

def clean_url(url: str) -> str:
    """Decode entities, strip tracking params, and normalize URL. Returns "" if not a valid http URL."""
    if not url:
        return ""
    try:
        url = _decode_entities(url).strip().strip("'\"")
        # Handle truncated URLs ending with ... (from HN story_text) - keep as is but clean what we can
        is_truncated = url.endswith("...") or url.endswith("…")
        # Remove trailing punctuation that is not part of URL when truncated
        # Parse
        parsed = urlparse(url if not is_truncated else url.rstrip(".…"))
        if parsed.scheme not in ("http", "https"):
            return ""
        # Filter tracking params
        qsl = parse_qsl(parsed.query, keep_blank_values=True)
        filtered = [(k, v) for k, v in qsl if k.lower() not in _TRACKING_PARAMS]
        new_query = urlencode(filtered, doseq=True)
        cleaned = urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))
        if is_truncated and not cleaned.endswith("..."):
            cleaned += "..."
        # Remove empty ? if no query left
        if cleaned.endswith("?"):
            cleaned = cleaned[:-1]
        return cleaned
    except Exception:
        return url

def _extract_href_urls(html_text: str) -> list[str]:
    """Extract href values from <a> tags (decoded and cleaned)."""
    if not html_text or "<a" not in html_text.lower():
        return []
    # Find href="..."/href='...'
    href_re = re.compile(r'href\s*=\s*["\']([^"\']+)["\']', re.IGNORECASE)
    urls = []
    for m in href_re.finditer(html_text):
        raw = m.group(1)
        cleaned = clean_url(_decode_entities(raw))
        if cleaned:
            urls.append(cleaned)
    return urls

def html_to_text(html_text: str) -> str:
    """
    Convert HTML fragment to clean plain text.
    - Decodes entities, strips tags, collapses whitespace.
    - Extracts <a> link texts but not raw <a> markup.
    - Handles malformed HTML gracefully via regex fallback.
    """
    if not html_text:
        return ""
    # Decode first so tags become recognizable
    text = _decode_entities(html_text)
    # Replace block tags with newlines/spaces before stripping
    text = re.sub(r"</p\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<br\s*/?>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</div\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"</li\s*>", "\n", text, flags=re.IGNORECASE)
    text = re.sub(r"<li[^>]*>", "• ", text, flags=re.IGNORECASE)
    # Strip remaining tags
    text = _TAG_RE.sub(" ", text)
    # Fallback for malformed fragments without closing > (e.g., truncated HN: <a href="https://x.com/...)
    text = re.sub(r"<[^>\s]*", " ", text)
    # Decode again after stripping (in case entities were inside tags)
    text = _decode_entities(text)
    # Collapse whitespace and newlines
    text = _WS_RE.sub(" ", text)
    text = re.sub(r"\s*\n\s*", "\n", text)
    # Clean up spaces around punctuation and multiple newlines
    text = re.sub(r"\n{2,}", "\n", text)
    text = re.sub(r" \n", "\n", text)
    return text.strip()

def sanitize_content(raw_html: str, max_len: int = 800) -> str:
    """
    Sanitize HackerNews/GDELT style HTML fragments into human-readable plain text.
    - Decodes &#x2F;, &amp;, etc.
    - Strips <a href> but keeps link text; de-duplicates URLs that appear as both href and text
    - Removes tracking params from any URLs that remain in text
    - Truncates intelligently at sentence/word boundary
    """
    if not raw_html:
        return ""
    # Quick path: if no HTML markers, just decode and clean URLs in text
    if "<" not in raw_html and "&" not in raw_html:
        # Still clean URLs in plain text
        decoded = _decode_entities(raw_html)
        # Clean URLs inline
        def _replace_url(m):
            return clean_url(m.group(0))
        cleaned = _URL_RE.sub(_replace_url, decoded)
        cleaned = _WS_RE.sub(" ", cleaned).strip()
        if len(cleaned) > max_len:
            # Truncate at word boundary
            truncated = cleaned[:max_len].rsplit(" ", 1)[0]
            return truncated + "…"
        return cleaned

    # For HTML, replace <a> tags with their href (cleaned) when display is truncated URL
    decoded_html = _decode_entities(raw_html)

    def _anchor_replacer(m):
        href = m.group(1) or ""
        display = m.group(2) or ""
        href_clean = clean_url(_decode_entities(href))
        # display may still contain HTML (e.g., <i>); strip it for comparison
        display_text = html_to_text(display).strip() if display else ""
        # If display is a truncated URL that is prefix of href, prefer href
        if display_text.startswith("http"):
            disp_base = display_text.rstrip(".…").lower().rstrip("/")
            href_base = href_clean.rstrip(".…").lower().rstrip("/")
            if disp_base and href_base.startswith(disp_base) and len(href_clean) > len(display_text):
                return href_clean + " "
            if disp_base == href_base:
                return href_clean + " "
        if display_text:
            return display_text + " "
        return href_clean + " "

    # Well-formed <a href="...">display</a>
    decoded_html = re.sub(r'<a[^>]*href\s*=\s*["\']([^"\']+)["\'][^>]*>(.*?)</a>', _anchor_replacer, decoded_html, flags=re.IGNORECASE | re.DOTALL)
    # Malformed <a href="..."> without closing > or </a> (e.g., truncated HN) — handle missing closing quote or >
    decoded_html = re.sub(r'<a[^>]*href\s*=\s*["\']([^"\']+)["\']?[^>]*>?', lambda m: clean_url(_decode_entities(m.group(1))) + " ", decoded_html, flags=re.IGNORECASE)
    # Handle truncated href without closing quote at all (HN truncates mid-URL)
    decoded_html = re.sub(r'<a[^>]*href\s*=\s*["\']?(https?://[^"\'>\s]+)', lambda m: clean_url(_decode_entities(m.group(1))) + " ", decoded_html, flags=re.IGNORECASE)

    text = html_to_text(decoded_html)

    # Clean any URLs that remain in the text (they are now plain text, but may still have tracking)
    def _clean_url_match(m):
        url = m.group(0)
        # If this URL's base matches a href we already have, it might be duplicate display text; keep one
        cleaned = clean_url(url)
        return cleaned

    text = _URL_RE.sub(_clean_url_match, text)

    # De-duplicate: if text contains same URL twice in a row (href text + href URL), collapse
    # Simple heuristic: split and dedup consecutive duplicate URLs
    parts = text.split()
    deduped_parts: list[str] = []
    seen_urls: set[str] = set()
    for part in parts:
        # Check if part is a URL
        if part.startswith("http"):
            base = part.lower().rstrip("/.…,")
            # Compare base without scheme
            try:
                p = urlparse(part)
                base_key = f"{p.netloc}{p.path}".lower().rstrip("/")
            except Exception:
                base_key = base
            if base_key in seen_urls:
                continue
            seen_urls.add(base_key)
        deduped_parts.append(part)
    text = " ".join(deduped_parts)

    # Final whitespace cleanup
    text = _WS_RE.sub(" ", text).strip()
    text = re.sub(r"\s*([.,;:!?])", r"\1", text)
    text = re.sub(r"\(\s+", "(", text)
    text = re.sub(r"\s+\)", ")", text)

    # Truncate at word boundary
    if len(text) > max_len:
        truncated = text[:max_len].rsplit(" ", 1)[0]
        # Avoid cutting inside URL
        if truncated.count("http") != text[:max_len].count("http"):
            # If we cut a URL, extend to include it or cut before it
            last_http = truncated.rfind("http")
            if last_http != -1:
                # Keep the URL if it started before max_len
                url_match = _URL_RE.search(text[last_http:])
                if url_match:
                    url_full = clean_url(url_match.group(0))
                    truncated = truncated[:last_http] + url_full
                    if len(truncated) > max_len + 100:
                        truncated = truncated[:max_len].rsplit(" ", 1)[0] + "…"
                        return truncated
        return truncated + "…"

    return text

def sanitize_title(raw_title: str) -> str:
    """Sanitize title: decode entities, strip tags, collapse whitespace."""
    if not raw_title:
        return ""
    # Titles should never contain HTML, but HN _highlightResult injects <em> tags
    t = _decode_entities(raw_title)
    t = _TAG_RE.sub("", t)
    t = _decode_entities(t)
    t = _WS_RE.sub(" ", t).strip()
    return t

def extract_primary_url(href_html: str, fallback_url: str) -> str:
    """
    Choose the best canonical URL for View source.
    - Prefer fallback_url (story_url) if it is a real http URL
    - Otherwise extract first href from html and clean it
    """
    fallback_clean = clean_url(fallback_url) if fallback_url else ""
    if fallback_clean and fallback_clean.startswith("http"):
        return fallback_clean
    hrefs = _extract_href_urls(href_html or "")
    if hrefs:
        return hrefs[0]
    # Fallback: extract any URL from text
    text = _decode_entities(href_html or "")
    m = _URL_RE.search(text)
    if m:
        return clean_url(m.group(0))
    return fallback_clean

def extract_companies(text: str) -> list[str]:
    """
    Extract organization names from text using COMPANY_DICT aliases + regex heuristics.
    Returns canonical company names from COMPANY_DICT where possible.
    """
    if not text:
        return []

    text_lower = text.lower()
    found_canonical = set()
    matched_words = set()  # Track individual words that are part of matched aliases

    # 1. First pass: Check COMPANY_DICT aliases (high precision) - longest first
    for alias_lower, canonical in _alias_entries:
        if alias_lower in text_lower:
            # Find all occurrences of this alias
            start = 0
            while True:
                idx = text_lower.find(alias_lower, start)
                if idx == -1:
                    break
                # Track individual words in this alias to exclude from regex pass
                alias_words = alias_lower.split()
                for word in alias_words:
                    matched_words.add(word)
                found_canonical.add(canonical)
                start = idx + 1

    # 2. Second pass: Regex for unknown companies (broad recall)
    matches = _COMPANY_PATTERN.findall(text)
    for m in matches:
        if m not in _STOPWORDS and len(m) > 2 and m not in _KNOWN_ACRONYMS:
            m_lower = m.lower()
            # Skip if this word was part of a matched multi-word alias
            if m_lower in matched_words:
                continue
            # If this matches a known alias, use canonical; otherwise use as-is
            canonical = _COMPANY_ALIAS_MAP.get(m_lower)
            if canonical:
                found_canonical.add(canonical)
            elif m_lower not in {c.lower() for c in found_canonical}:
                found_canonical.add(m)

    return list(found_canonical)

def get_primary_company(text: str) -> str | None:
    """Get the first/most relevant company from text, or None."""
    companies = extract_companies(text)
    return companies[0] if companies else None


# Unified event type classification keywords (snake_case labels)
_EVENT_TYPE_KEYWORDS = {
    # M&A
    "acquired": "m_and_a",
    "acquisition": "m_and_a",
    "acqu": "m_and_a",
    "bought": "m_and_a",
    "merger": "m_and_a",
    # Contract/Partnership
    "contract": "contract",
    "deal": "contract",
    "partnership": "contract",
    "partner": "contract",
    "collaborate": "contract",
    "joint": "contract",
    "agreement": "contract",
    # Product Launch
    "launch": "product_launch",
    "release": "product_launch",
    "launched": "product_launch",
    "unveiled": "product_launch",
    "announce": "product_launch",
    "open-source": "product_launch",
    # Supply Chain / Manufacturing
    "supply": "supply_chain",
    "yield": "supply_chain",
    "foundry": "supply_chain",
    "fab": "supply_chain",
    "produce": "supply_chain",
    "production": "supply_chain",
    "manufacturing": "supply_chain",
    "fabrication": "supply_chain",
    "shortage": "supply_chain",
    "capacity": "supply_chain",
    "export control": "supply_chain",
    "sanction": "supply_chain",
    # Financial
    "earnings": "financial",
    "revenue": "financial",
    "profit": "financial",
    "quarter": "financial",
    "stock": "financial",
    # AI / Tech
    "ai ": "product_launch",
    "artificial intelligence": "product_launch",
    "model": "product_launch",
    "gpt": "product_launch",
    "llama": "product_launch",
    "gemini": "product_launch",
    "llm": "product_launch",
}

def classify_event_type(title: str, content: str = "") -> str:
    """
    Classify event type based on title and content keywords.
    Returns snake_case event type (m_and_a, contract, product_launch, supply_chain, financial, general).
    """
    if not title and not content:
        return "general"

    text = (title + " " + content).lower()

    # Check keywords in priority order (more specific first)
    for keyword, event_type in _EVENT_TYPE_KEYWORDS.items():
        if keyword in text:
            return event_type

    return "general"

def get_current_timestamp() -> str:
    """Get current timestamp in ISO format"""
    return datetime.utcnow().isoformat() + "Z"

def now_ts() -> str:
    """Return current UTC timestamp string (alias for get_current_timestamp)."""
    return get_current_timestamp()

def validate_api_key(api_key: str) -> bool:
    """Validate API key format"""
    if not api_key or len(api_key) < 10:
        return False
    return True

def format_error_response(message: str, code: str = "ERROR") -> dict[str, Any]:
    """Format error response"""
    return {
        "error": code,
        "message": message,
        "timestamp": get_current_timestamp()
    }

def normalize_text(text: str) -> str:
    """Normalize text for deduplication (lowercase, strip, remove extra spaces/punctuation)"""
    if not text:
        return ""
    # Lowercase and strip
    text = text.lower().strip()
    # Remove special chars but keep alphanumeric
    text = re.sub(r'[^\w\s]', '', text)
    # Collapse multiple spaces
    text = re.sub(r'\s+', ' ', text)
    return text

def compute_event_id(event: dict) -> str:
    """
    Generate SHA256 fingerprint from normalized title + url/content + source.
    Robust against minor formatting differences.
    """
    title = normalize_text(event.get('title', ''))
    source = normalize_text(event.get('source', ''))

    # Prefer URL for uniqueness if available
    url = event.get('url', '')
    if url:
        unique_str = f"{title}|{url}|{source}"
    else:
        # Fallback to content snippet
        content = normalize_text(event.get('content', ''))[:200]
        unique_str = f"{title}|{content}|{source}"

    return hashlib.sha256(unique_str.encode()).hexdigest()

def parse_timestamp(ts: Any) -> datetime:
    """Parse ISO timestamp with fallback"""
    try:
        if not ts or not isinstance(ts, str):
            return datetime.utcnow()
        # Handle "Z" suffix
        if ts.endswith('Z'):
            ts = ts[:-1]
        return datetime.fromisoformat(ts)
    except (ValueError, TypeError, Exception):
        # Fallback to now if invalid
        return datetime.utcnow()

def is_fresh(timestamp: str, hours: int = 12) -> bool:
    """Check if event is within freshness window"""
    if not timestamp:
        return False

    event_time = parse_timestamp(timestamp)
    cutoff_time = datetime.utcnow() - timedelta(hours=hours)

    return event_time > cutoff_time

def compute_recency_boost(timestamp: str, max_boost: int = 50) -> int:
    """
    Calculate recency boost (exponential decay).
    Events < 1h old get max_boost.
    Events > 24h old get 0.
    """
    if not timestamp:
        return 0

    event_time = parse_timestamp(timestamp)
    age_hours = (datetime.utcnow() - event_time).total_seconds() / 3600

    if age_hours < 0: # Future timestamp
        return max_boost
    if age_hours > 24:
        return 0

    # Linear decay for simplicity (can be exponential if needed)
    # 0h -> 50, 12h -> 25, 24h -> 0
    boost = max_boost * (1 - (age_hours / 24))
    return int(max(0, boost))

def deduplicate_and_append(new_events: list[dict], file_path: Path) -> int:
    """
    Append new events to the file only if they don't already exist in SQLite store.
    Returns the number of new events added.
    Also enqueues embeddings for the vector store (best-effort, async).
    """
    if not new_events:
        return 0

    added_count = 0
    events_to_write = []

    for event in new_events:
        # Sanitize before dedup so IDs are based on clean text (fixes legacy &#x2F; duplicates)
        try:
            if event.get("title"):
                event["title"] = sanitize_title(str(event["title"]))
            if event.get("content"):
                event["content"] = sanitize_content(str(event["content"]), max_len=2000)
            if event.get("snippet"):
                event["snippet"] = sanitize_content(str(event["snippet"]), max_len=600)
            if event.get("url"):
                cleaned = clean_url(str(event["url"]))
                if cleaned:
                    event["url"] = cleaned
        except Exception:
            pass
        event_id = compute_event_id(event)

        # Check if seen in DB
        if not storage.is_duplicate(event_id):
            # Mark as seen
            storage.mark_seen(event_id, event.get('source', 'unknown'), event.get('title', ''))
            events_to_write.append(event)
            added_count += 1

    if events_to_write:
        # Ensure parent dir exists
        file_path.parent.mkdir(parents=True, exist_ok=True)

        with open(file_path, "a", encoding="utf-8") as f:
            for event in events_to_write:
                json.dump(event, f, ensure_ascii=False)
                f.write("\n")

        # Best-effort async embedding + vector upsert
        try:
            import asyncio

            from .services.vector_store import is_available

            if is_available():
                texts = [
                    f"{e.get('title','')}. {e.get('content') or e.get('snippet','')}"[:2000]
                    for e in events_to_write
                ]
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(_embed_and_store(events_to_write, texts))
                except RuntimeError:
                    # no running loop (sync context like scheduler thread)
                    threading.Thread(
                        target=lambda: asyncio.run(_embed_and_store(events_to_write, texts)),
                        daemon=True,
                    ).start()
        except Exception as e:
            logger.debug(f"Vector indexing skipped: {e}")

        # Publish to Redis Pub/Sub for WebSockets
        try:
            import os
            from app.settings import settings
            url = (settings.redis_url or os.getenv("REDIS_URL", "")).strip()
            if url and url != "memory://":
                import redis
                client = redis.Redis.from_url(url, decode_responses=True, socket_timeout=1)
                # Publish JSON payload containing the new events
                client.publish("siliconpulse:signals", json.dumps({"events": events_to_write}, default=str))
        except Exception as e:
            logger.debug(f"Failed to publish to redis: {e}")

    return added_count


async def _embed_and_store(events: list[dict], texts: list[str]) -> None:
    try:
        from .services.embedding_service import embed_texts
        from .services.vector_store import upsert_signals

        embs = await embed_texts(texts)
        if any(embs):
            n = upsert_signals(events, embs)
            logger.info(f"Vector indexed {n} new signals")
    except Exception as e:
        logger.debug(f"Embed/store failed: {e}")

def safe_read_jsonl(path: Path, limit: int = 200, freshness_hours: int | None = None) -> list[dict]:
    """
    Safely read JSONL file, ignoring errors and returning valid events.
    Optionally filters by freshness.
    """
    events = []
    try:
        if not path.exists():
            return []

        # If filtering by freshness, we might need to read more lines to find enough fresh ones
        # So we read more if freshness filter is active
        read_limit = limit * 5 if freshness_hours else limit

        # PATHWAY INTEGRATION: Check if we should read from pathway output instead
        from app.settings import settings
        if settings.use_pathway:
            pathway_path = settings.resolved_pathway_path
            if pathway_path.exists() and pathway_path.stat().st_size > 0:
                path = pathway_path
                # logger.info(f"Reading from Pathway output: {path}")

        with open(path, encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
            # Take last 'read_limit' lines
            recent_lines = all_lines[-read_limit:] if len(all_lines) > read_limit else all_lines

            # Process in reverse to get newest first, then reverse back
            for line in reversed(recent_lines):
                line = line.strip()
                if not line:
                    continue
                try:
                    event = json.loads(line)
                    if isinstance(event, dict):
                        title = str(event.get("title") or "").strip()
                        if not title:
                            continue

                        event.setdefault("timestamp", get_current_timestamp())
                        event.setdefault("source", "Unknown")
                        event.setdefault("snippet", str(event.get("content") or title)[:300])
                        event.setdefault("content", event.get("snippet") or title)

                        # Sanitize legacy HTML artifacts (HackerNews &#x2F; + <a href> + utm_) on read
                        try:
                            if event.get("title"):
                                event["title"] = sanitize_title(str(event["title"]))
                            if event.get("content"):
                                event["content"] = sanitize_content(str(event["content"]), max_len=2000)
                            if event.get("snippet"):
                                event["snippet"] = sanitize_content(str(event["snippet"]), max_len=600)
                            if event.get("url"):
                                cleaned = clean_url(str(event["url"]))
                                if cleaned:
                                    event["url"] = cleaned
                            if event.get("source"):
                                event["source"] = sanitize_title(str(event["source"]))
                        except Exception:
                            pass

                        if freshness_hours is not None and not is_fresh(event.get("timestamp", ""), freshness_hours):
                            continue

                        events.append(event)
                        if len(events) >= limit:
                            break
                except Exception:
                    continue

        # Reverse back to chronological order (oldest to newest) if that's what caller expects
        # But usually for display we want newest first.
        # The original function returned chronological (append order).
        # Let's keep original behavior: return chronological order.
        return events
    except Exception as e:
        logger.error(f"Error reading JSONL: {e}")
        return []

def compute_confidence(evidence: list) -> dict:
    """
    Compute dynamic confidence score (0-100), label, and reason.

    Rules:
    - Evidence Count: >=6 (+50), 3-5 (+30), 1-2 (+15), 0 (+0)
    - Recency: Latest evidence < 2h (+25), < 12h (+15), else (+5)
    - Source Reliability: High trust (+15), Medium (+10), Low (+5)
    """
    if not evidence:
        return {
            "score": 0,
            "label": "LOW",
            "reason": "No evidence found in current data stream."
        }

    score = 0
    count = len(evidence)

    # 1. Evidence Count
    if count >= 6:
        score += 50
    elif count >= 3:
        score += 30
    elif count >= 1:
        score += 15

    # 2. Recency Factor
    try:
        # Sort evidence by timestamp to find the latest
        sorted_ev = sorted(evidence, key=lambda x: parse_timestamp(x.timestamp) if hasattr(x, 'timestamp') and x.timestamp else datetime.min, reverse=True)
        latest_ts = sorted_ev[0].timestamp if sorted_ev and hasattr(sorted_ev[0], 'timestamp') else None

        if latest_ts:
            latest_time = parse_timestamp(latest_ts)
            age_hours = (datetime.utcnow() - latest_time).total_seconds() / 3600

            if age_hours < 2:
                score += 25
            elif age_hours < 12:
                score += 15
            else:
                score += 5
        else:
            score += 5
    except Exception as e:
        logger.warning(f"Error computing recency for confidence: {e}")
        score += 5

    # 3. Source Reliability
    # High trust: Reuters, Bloomberg, Official, etc.
    # Medium: Perplexity, TechCrunch, etc.
    # Low: X, Rumor, etc.
    high_trust = ["reuters", "bloomberg", "official", "press release", "sec", "nasdaq"]
    med_trust = ["perplexity", "techcrunch", "verge", "wired", "wsj", "nyt"]

    sources = [str(e.source).lower() if hasattr(e, 'source') else "" for e in evidence]

    source_boost = 5 # Default low
    for s in sources:
        if any(ht in s for ht in high_trust):
            source_boost = 15
            break
        if any(mt in s for mt in med_trust):
            source_boost = max(source_boost, 10)

    score += source_boost

    # Clamp
    score = min(100, score)

    # Label
    if score >= 70:
        label = "HIGH"
    elif score >= 40:
        label = "MEDIUM"
    else:
        label = "LOW"

    # Reason
    recency_str = "very recent" if score >= 25 else "recent" if score >= 15 else "older"
    source_str = "reliable" if source_boost == 15 else "mixed" if source_boost == 10 else "unverified"

    reason = f"{count} evidence items found, latest is {recency_str}, {source_str} sources."

    return {
        "score": score,
        "label": label,
        "reason": reason
    }

def get_trust_info(source_name: str) -> dict:
    """
    Get trust level and reason for a given source.
    """
    source_lower = source_name.lower()

    # High Trust Sources
    high_trust = ["reuters", "bloomberg", "sec", "official", "press release", "cnbc", "wsj"]
    for s in high_trust:
        if s in source_lower:
            return {"trust_level": "High", "reason": "Verified institutional news source"}

    # Medium Trust Sources
    medium_trust = ["perplexity", "marketwire", "techcrunch", "the verge", "engadget"]
    for s in medium_trust:
        if s in source_lower:
            return {"trust_level": "Medium", "reason": "Reputable tech/market aggregator"}

    # Low Trust Sources
    low_trust = ["x", "twitter", "reddit", "blog", "social", "unverified"]
    for s in low_trust:
        if s in source_lower:
            return {"trust_level": "Low", "reason": "Social media or unverified community signal"}

    return {"trust_level": "Low", "reason": "Unknown or unverified source"}
