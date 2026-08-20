from __future__ import annotations

import hashlib
from datetime import datetime


class QueryCache:
    """LRU cache for query results with TTL"""

    def __init__(self, ttl_seconds: int = 60, max_size: int = 100):
        self.ttl_seconds = ttl_seconds
        self.cache: dict[str, tuple[dict, datetime]] = {}
        self.max_size = max_size

    def _make_key(self, query: str, k: int) -> str:
        """Create cache key from query and k"""
        normalized = query.lower().strip()
        key_str = f"{normalized}:{k}"
        return hashlib.md5(key_str.encode()).hexdigest()

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

    def clear(self):
        """Clear all cached results"""
        self.cache.clear()

# Global query cache instance
query_cache = QueryCache(ttl_seconds=60, max_size=100)
