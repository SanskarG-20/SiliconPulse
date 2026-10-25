"""Indexed local search and deterministic RRF/reranking helpers."""
from __future__ import annotations

import json
import logging
import re
import sqlite3
import threading
from pathlib import Path

from ..settings import settings

logger = logging.getLogger(__name__)
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_INDEX_LOCK = threading.Lock()


def _tokens(text: str) -> list[str]:
    return list(dict.fromkeys(token.lower() for token in _TOKEN_RE.findall(text) if len(token) > 1))


def _connection():
    from ..supabase_client import is_supabase_enabled

    if is_supabase_enabled() or settings.app_env.lower() == "production":
        return None
    from ..storage import get_db_connection
    return get_db_connection()


def _index_schema(connection):
    connection.execute(
        """CREATE VIRTUAL TABLE IF NOT EXISTS local_signal_search USING fts5(
            title, content, company, event_id UNINDEXED, source UNINDEXED,
            timestamp UNINDEXED, url UNINDEXED, event_type UNINDEXED,
            tokenize='unicode61'
        )"""
    )


def _event_id(event: dict) -> str:
    from ..utils import compute_event_id
    return str(event.get("event_id") or compute_event_id(event))


def _insert_events(connection, events: list[dict]) -> None:
    for event in events:
        event_id = _event_id(event)
        exists = connection.execute(
            "SELECT 1 FROM local_signal_search WHERE event_id = ? LIMIT 1", (event_id,)
        ).fetchone()
        if exists:
            continue
        connection.execute(
            "INSERT INTO local_signal_search(title, content, company, event_id, source, timestamp, url, event_type) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                str(event.get("title") or ""),
                str(event.get("content") or event.get("snippet") or ""),
                str(event.get("company") or ""), event_id,
                str(event.get("source") or "Unknown"), str(event.get("timestamp") or ""),
                str(event.get("url") or ""), str(event.get("event_type") or "general"),
            ),
        )


def _bootstrap(connection, data_path: Path) -> None:
    count = connection.execute("SELECT count(*) FROM local_signal_search").fetchone()[0]
    if count:
        return
    try:
        with data_path.open(encoding="utf-8", errors="replace") as source:
            events = []
            for line in source:
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    continue
                if isinstance(item, dict):
                    events.append(item)
        _insert_events(connection, events)
        connection.commit()
    except OSError:
        logger.debug("Local signal search index has no JSONL corpus to bootstrap")


def index_local_events(events: list[dict]) -> None:
    """Update the local-dev FTS cache as signals are ingested."""
    try:
        connection = _connection()
        if connection is None:
            return
        with _INDEX_LOCK:
            _index_schema(connection)
            _insert_events(connection, events)
            connection.commit()
    except (sqlite3.Error, RuntimeError) as exc:
        logger.debug("Local FTS indexing unavailable: %s", exc)


def search_local_signals(query: str, data_path: Path, limit: int = 200) -> list[dict] | None:
    """Return indexed keyword hits; None means local FTS is unavailable."""
    terms = _tokens(query)
    if not terms:
        return []
    try:
        connection = _connection()
        if connection is None:
            return None
        with _INDEX_LOCK:
            _index_schema(connection)
            _bootstrap(connection, Path(data_path))
            expression = " OR ".join('"' + term.replace('"', '""') + '"' for term in terms)
            rows = connection.execute(
                "SELECT title, content, company, event_id, source, timestamp, url, event_type, bm25(local_signal_search) AS rank "
                "FROM local_signal_search WHERE local_signal_search MATCH ? ORDER BY rank LIMIT ?",
                (expression, max(1, min(int(limit), 5000))),
            ).fetchall()
        return [
            {"title": row[0], "content": row[1], "company": row[2], "event_id": row[3],
             "source": row[4], "timestamp": row[5], "url": row[6], "event_type": row[7],
             "keyword_rank": index + 1}
            for index, row in enumerate(rows)
        ]
    except (sqlite3.Error, RuntimeError) as exc:
        logger.debug("Local FTS search unavailable: %s", exc)
        return None


def _key(item: dict) -> str:
    return str(item.get("event_id") or "|".join((str(item.get("title") or "").lower(), str(item.get("source") or "").lower())))


def reciprocal_rank_fusion(*ranked_lists: list[dict], limit: int = 100, rrf_k: int = 60) -> list[dict]:
    """Fuse keyword/vector ranks with standard reciprocal rank fusion."""
    fused: dict[str, dict] = {}
    scores: dict[str, float] = {}
    for ranked in ranked_lists:
        for rank, item in enumerate(ranked, start=1):
            key = _key(item)
            if key not in fused:
                fused[key] = dict(item)
            else:
                fused[key].update({name: value for name, value in item.items() if value not in (None, "")})
            scores[key] = scores.get(key, 0.0) + 1.0 / (rrf_k + rank)
    for key, item in fused.items():
        item["rank_score"] = scores[key]
    ordered = sorted(fused.values(), key=lambda item: item["rank_score"], reverse=True)
    return ordered[:max(1, limit)]


def rerank_results(query: str, candidates: list[dict], limit: int = 100) -> list[dict]:
    """Rerank fused candidates using query-term coverage and original retrieval score."""
    query_terms = set(_tokens(query))
    for item in candidates:
        title_terms = set(_tokens(str(item.get("title") or "")))
        body_terms = set(_tokens(" ".join(str(item.get(key) or "") for key in ("content", "snippet", "company"))))
        coverage = len(query_terms & (title_terms | body_terms)) / max(1, len(query_terms))
        title_coverage = len(query_terms & title_terms) / max(1, len(query_terms))
        base = float(item.get("rank_score") or item.get("similarity") or 0.0)
        item["rerank_score"] = round(0.65 * base + 0.25 * coverage + 0.10 * title_coverage, 6)
    return sorted(candidates, key=lambda item: item["rerank_score"], reverse=True)[:max(1, limit)]
