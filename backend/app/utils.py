"""
Utility functions for SiliconPulse backend
"""
from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

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
