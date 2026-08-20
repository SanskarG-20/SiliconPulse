from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from .settings import settings

logger = logging.getLogger(__name__)

class EventCache:
    """In-memory cache for recent events to speed up query retrieval"""

    def __init__(self, max_events: int = 2000):
        self.max_events = max_events
        self.events: list[dict] = []
        self.last_refresh: datetime | None = None
        self.refresh_interval = 3  # seconds

    def should_refresh(self) -> bool:
        """Check if cache needs refresh"""
        if self.last_refresh is None:
            return True
        elapsed = (datetime.utcnow() - self.last_refresh).total_seconds()
        return elapsed >= self.refresh_interval

    def refresh(self, file_path: Path, freshness_hours: int | None = None):
        """Refresh cache from file"""
        try:
            if not file_path.exists():
                self.events = []
                self.last_refresh = datetime.utcnow()
                return

            events = []
            cutoff_time = None
            if freshness_hours:
                cutoff_time = datetime.utcnow() - timedelta(hours=freshness_hours)

            # Read last N events from file
            with open(file_path, encoding="utf-8") as f:
                lines = f.readlines()

            # Process from end (most recent first)
            for line in reversed(lines[-self.max_events:]):
                if not line.strip():
                    continue
                try:
                    event = json.loads(line)

                    # Apply freshness filter if specified
                    if cutoff_time and event.get("timestamp"):
                        try:
                            event_time = datetime.fromisoformat(event["timestamp"].replace("Z", "+00:00"))
                            if event_time.replace(tzinfo=None) < cutoff_time:
                                continue
                        except Exception:
                            pass

                    events.append(event)
                except json.JSONDecodeError:
                    continue

            self.events = events
            self.last_refresh = datetime.utcnow()
            logger.info(f"Event cache refreshed: {len(self.events)} events loaded")

        except Exception as e:
            logger.error(f"Error refreshing event cache: {e}")
            self.events = []
            self.last_refresh = datetime.utcnow()

    def get_events(self, file_path: Path, freshness_hours: int | None = None) -> list[dict]:
        """Get cached events, refreshing if needed"""
        if self.should_refresh():
            self.refresh(file_path, freshness_hours)
        return self.events

# Global cache instance
event_cache = EventCache(max_events=settings.max_events_to_scan)
