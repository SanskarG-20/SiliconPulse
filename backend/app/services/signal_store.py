"""Canonical signal persistence backed by Supabase Postgres in hosted environments."""
from __future__ import annotations

from typing import Any

from ..supabase_client import get_supabase_client, is_supabase_enabled
from ..utils import clean_url, compute_event_id, sanitize_content, sanitize_title


def is_enabled() -> bool:
    return is_supabase_enabled()


def _client():
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase signal storage is configured but unavailable")
    return client


def insert_events(events: list[dict]) -> list[dict]:
    """Atomically insert unseen signals and return only newly accepted payloads."""
    if not events:
        return []
    cleaned = []
    for original in events:
        event = dict(original)
        if event.get("title"):
            event["title"] = sanitize_title(str(event["title"]))
        if event.get("content"):
            event["content"] = sanitize_content(str(event["content"]), max_len=2000)
        if event.get("snippet"):
            event["snippet"] = sanitize_content(str(event["snippet"]), max_len=600)
        if event.get("url"):
            event["url"] = clean_url(str(event["url"])) or event["url"]
        cleaned.append(event)
    records = [{"event_id": compute_event_id(event), "payload": event} for event in cleaned]
    result = _client().rpc("ingest_market_signals", {"p_events": records}).execute()
    return [
        row.get("payload")
        for row in (result.data or [])
        if isinstance(row, dict) and isinstance(row.get("payload"), dict)
    ]


def list_events(limit: int = 200) -> list[dict]:
    result = _client().rpc(
        "list_market_signals", {"p_limit": max(1, min(int(limit), 5000))}
    ).execute()
    return [
        row["payload"]
        for row in (result.data or [])
        if isinstance(row, dict) and isinstance(row.get("payload"), dict)
    ]


def count_events() -> int:
    result = _client().rpc("market_signal_count", {}).execute()
    data = result.data
    if isinstance(data, int):
        return data
    if isinstance(data, list) and data:
        return int(data[0].get("market_signal_count", 0)) if isinstance(data[0], dict) else int(data[0])
    return 0


def get_checkpoint(source: str) -> str | None:
    result = (
        _client().table("ingestion_checkpoints")
        .select("last_checkpoint")
        .eq("source", source)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return str(rows[0]["last_checkpoint"]) if rows else None


def set_checkpoint(source: str, checkpoint: str) -> None:
    _client().table("ingestion_checkpoints").upsert(
        {"source": source, "last_checkpoint": checkpoint}, on_conflict="source"
    ).execute()


def check_ready() -> None:
    """Fail fast when required canonical tables/RPCs are not deployed."""
    client = _client()
    client.rpc("market_signal_count", {}).execute()
    client.table("signals_vec").select("id").limit(1).execute()
    client.table("ingestion_checkpoints").select("source").limit(1).execute()
    client.table("websocket_tickets").select("ticket_hash").limit(1).execute()
