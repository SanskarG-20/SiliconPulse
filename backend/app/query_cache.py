from __future__ import annotations

import hashlib
import json
from datetime import datetime


class QueryCache:
    """LRU cache for query results with TTL"""

    def __init__(self, ttl_seconds: int = 60, max_size: int = 100, report_ttl_seconds: int = 300):
        self.ttl_seconds = ttl_seconds
        self.report_ttl_seconds = report_ttl_seconds
        self.cache: dict[str, tuple[dict, datetime]] = {}
        self.max_size = max_size
        self.report_cache: dict[str, tuple[str, datetime]] = {}

    def _make_key(self, query: str, k: int) -> str:
        """Create cache key from query and k"""
        normalized = query.lower().strip()
        key_str = f"{normalized}:{k}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    def get(self, query: str, k: int) -> dict | None:
        """Get cached result if valid"""
        key = self._make_key(query, k)

        if key not in self.cache:
            return None

        result, timestamp = self.cache[key]

        # Check if expired
        if (datetime.utcnow() - timestamp).total_seconds() > self.ttl_seconds:
            del self.cache[key]
            return None

        return result

    def set(self, query: str, k: int, result: dict):
        """Cache a query result"""
        key = self._make_key(query, k)

        # Implement simple LRU: if cache is full, remove oldest
        if len(self.cache) >= self.max_size:
            oldest_key = min(self.cache.keys(), key=lambda k: self.cache[k][1])
            del self.cache[oldest_key]

        self.cache[key] = (result, datetime.utcnow())

    @staticmethod
    def _make_report_key(query: str, evidence_hash: str) -> str:
        normalized = " ".join(query.casefold().split())
        payload = json.dumps([normalized, evidence_hash], separators=(",", ":"), ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()

    def get_report(self, query: str, evidence_hash: str) -> str | None:
        key = self._make_report_key(query, evidence_hash)
        cached = self.report_cache.get(key)
        if cached is None:
            return None
        report, timestamp = cached
        if (datetime.utcnow() - timestamp).total_seconds() > self.report_ttl_seconds:
            self.report_cache.pop(key, None)
            return None
        return report

    def set_report(self, query: str, evidence_hash: str, report: str) -> None:
        key = self._make_report_key(query, evidence_hash)
        if len(self.report_cache) >= self.max_size:
            oldest_key = min(self.report_cache, key=lambda item: self.report_cache[item][1])
            self.report_cache.pop(oldest_key, None)
        self.report_cache[key] = (report, datetime.utcnow())

    def clear(self):
        """Clear all cached results"""
        self.cache.clear()
        self.report_cache.clear()

# Global query cache instance
query_cache = QueryCache(ttl_seconds=60, max_size=100)
