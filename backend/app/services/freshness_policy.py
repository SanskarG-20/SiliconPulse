"""Deterministic freshness windows based on query intent and signal type."""
from __future__ import annotations

import re
from datetime import datetime, timezone

_HISTORY_TERMS = re.compile(r"\b(history|historical|timeline|over time|background|overview|since \d{4}|\d{4})\b", re.I)
_LATEST_TERMS = re.compile(r"\b(latest|today|now|current|currently|breaking|right now|this week|recent|last 24 hours?)\b", re.I)
_WEEK_TERMS = re.compile(r"\b(last|past|previous) week\b", re.I)
_MONTH_TERMS = re.compile(r"\b(last|past|previous) month\b", re.I)


def query_intent(query: str) -> str:
    if _HISTORY_TERMS.search(query or ""):
        return "historical"
    if _MONTH_TERMS.search(query or ""):
        return "month"
    if _WEEK_TERMS.search(query or ""):
        return "week"
    if _LATEST_TERMS.search(query or ""):
        return "latest"
    return "general"


def source_type(event: dict) -> str:
    source = str(event.get("source") or "").lower()
    event_type = str(event.get("event_type") or "").lower()
    combined = f"{source} {event_type}"
    if any(term in combined for term in ("sec", "edgar", "filing", "regulatory", "10-k", "10-q")):
        return "regulatory"
    if any(term in combined for term in ("official", "press release", "company announcement", "investor relations")):
        return "official"
    return "news"


def freshness_window_hours(query: str, event: dict, default_hours: int = 12) -> int | None:
    """Return the maximum age for an item; None means an explicit historical query."""
    intent = query_intent(query)
    if intent == "historical":
        return None
    kind = source_type(event)
    if intent == "week":
        return 168
    if intent == "month":
        return 720
    if intent == "latest":
        return {"news": max(1, default_hours), "official": 72, "regulatory": 168}[kind]
    return {"news": 72, "official": 336, "regulatory": 720}[kind]


def is_within_window(timestamp: str, hours: int, now: datetime | None = None) -> bool:
    if not timestamp:
        return False
    try:
        event_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if event_time.tzinfo is None:
            event_time = event_time.replace(tzinfo=timezone.utc)
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            current = current.replace(tzinfo=timezone.utc)
        age = (current - event_time.astimezone(timezone.utc)).total_seconds() / 3600
        return 0 <= age <= hours
    except (TypeError, ValueError):
        return False


def filter_by_freshness(query: str, events: list[dict], default_hours: int = 12) -> list[dict]:
    """Filter to adaptive windows, with explicit stale fallback when no hits qualify."""
    intent = query_intent(query)
    if intent == "historical":
        for event in events:
            event["freshness_status"] = "historical_query"
            event["freshness_window_hours"] = None
        return events
    matching = []
    for event in events:
        window = freshness_window_hours(query, event, default_hours)
        event["freshness_window_hours"] = window
        if window is None or is_within_window(str(event.get("timestamp") or ""), window):
            event["freshness_status"] = "within_window"
            matching.append(event)
    if matching:
        return matching
    for event in events:
        event["freshness_status"] = "outside_window_fallback"
    return events
