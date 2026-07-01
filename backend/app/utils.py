"""
Utility functions for SiliconPulse backend
"""
from datetime import datetime, timedelta
from typing import Any, Optional
import json
import hashlib
import re
from pathlib import Path
import logging

# Import storage module (circular import avoidance handled by function calls)
# We'll import inside functions where needed or rely on caller to pass dependencies if strict separation required
# But for this app structure, direct import is fine as storage doesn't import utils
from . import storage

logger = logging.getLogger(__name__)

import re

def extract_companies(text: str) -> list[str]:
    """
    Extract organization names from text using basic regex heuristics.
    (Spacy was blocked by Windows Application Control policies).
    """
    if not text:
        return []
        
    # Matches consecutive capitalized words, optionally with & or -
    pattern = r'\b[A-Z][a-zA-Z0-9]+(?: [&-] [A-Z][a-zA-Z0-9]+)*\b'
    matches = re.findall(pattern, text)
    
    # Filter out common stop words that get capitalized at sentence starts
    stopwords = {"The", "A", "An", "In", "On", "At", "To", "From", "By", "With", "As", "It", "This", "That", "For", "But", "And", "Or", "If", "When"}
    
    companies = []
    for m in matches:
        if m not in stopwords and len(m) > 2:
            companies.append(m)
            
    # Deduplicate while preserving order
    seen = set()
    unique = []
    for c in companies:
        cl = c.lower()
        if cl not in seen:
            seen.add(cl)
            unique.append(c)
            
    return unique

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
                


def safe_read_jsonl(path: Path, limit: int = 200, freshness_hours: Optional[int] = None) -> list[dict]:
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
            
        with open(path, "r", encoding="utf-8", errors="ignore") as f:
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
