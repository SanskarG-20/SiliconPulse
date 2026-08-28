"""
Supabase pgvector store for SiliconPulse signals.
Uses signals_vec table (vector(768)) + match_signals RPC.
Graceful no-op when Supabase not configured or pgvector not enabled.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def _get_supabase():
    try:
        from app.supabase_client import get_supabase_client, is_supabase_enabled

        if not is_supabase_enabled():
            return None
        client = get_supabase_client()
        if client is None:
            return None
        # Quick check: does signals_vec exist? Try a count RPC
        try:
            client.table("signals_vec").select("id").limit(1).execute()
        except Exception as e:
            # Table may not exist yet (user hasn't run SQL). Fall back to Chroma.
            if "does not exist" in str(e) or "relation" in str(e).lower():
                logger.debug(f"pgvector table not found, falling back to Chroma: {e}")
                return None
        return client
    except Exception as e:
        logger.debug(f"pgvector unavailable: {e}")
        return None


def is_available() -> bool:
    return _get_supabase() is not None


def count() -> int:
    client = _get_supabase()
    if client is None:
        return -1
    try:
        # Try RPC first, then direct count
        try:
            res = client.rpc("signals_vec_count", {}).execute()
            if res.data is not None:
                # res.data may be int or list
                if isinstance(res.data, int):
                    return int(res.data)
                if isinstance(res.data, list) and res.data:
                    return int(res.data[0].get("count", 0) if isinstance(res.data[0], dict) else res.data[0])
        except Exception:
            pass
        res = client.table("signals_vec").select("id", count="exact").limit(1).execute()
        # supabase-py returns count in res.count
        if hasattr(res, "count") and res.count is not None:
            return int(res.count)
        return len(res.data or [])
    except Exception as e:
        logger.debug(f"pgvector count failed: {e}")
        return -1


def upsert_signals(events: list[dict], embeddings: list[list[float]]) -> int:
    if not events or not embeddings:
        return 0
    client = _get_supabase()
    if client is None:
        return 0
    try:
        rows = []
        for ev, emb in zip(events, embeddings):
            if not emb:
                continue
            from app.utils import compute_event_id

            eid = compute_event_id(ev)
            rows.append(
                {
                    "id": eid,
                    "embedding": emb,
                    "document": f"{ev.get('title','')} {ev.get('content') or ev.get('snippet','')}"[:2000],
                    "metadata": {
                        "title": ev.get("title", "")[:500],
                        "source": ev.get("source", "Unknown")[:100],
                        "timestamp": ev.get("timestamp", ""),
                        "company": (ev.get("company") or "")[:100],
                        "event_type": (ev.get("event_type") or "general")[:50],
                        "url": (ev.get("url") or "")[:500],
                    },
                }
            )
        if not rows:
            return 0
        # supabase upsert
        client.table("signals_vec").upsert(rows, on_conflict="id").execute()
        return len(rows)
    except Exception as e:
        logger.warning(f"pgvector upsert failed: {e}")
        return 0


def query_similar(query_embedding: list[float], k: int = 10) -> list[dict]:
    client = _get_supabase()
    if client is None or not query_embedding:
        return []
    try:
        res = client.rpc("match_signals", {"query_embedding": query_embedding, "match_count": k}).execute()
        data = res.data or []
        out = []
        for row in data:
            meta = row.get("metadata", {}) if isinstance(row, dict) else {}
            # Ensure expected keys
            item = dict(meta)
            item["similarity"] = round(float(row.get("similarity", 0.0)), 4)
            item["distance"] = round(1.0 - float(row.get("similarity", 0.0)), 4)
            item["content"] = row.get("document", "")
            # Also ensure title/source etc are present
            if "title" not in item:
                item["title"] = row.get("document", "")[:200]
            out.append(item)
        return out
    except Exception as e:
        logger.warning(f"pgvector query failed: {e}")
        return []


def query_hybrid(query_text: str, query_embedding: list[float], k: int = 20) -> list[dict]:
    """
    Perform hybrid search using the match_signals_hybrid RPC (RRF combining semantic + full text).
    """
    client = _get_supabase()
    if client is None or not query_embedding or not query_text:
        return []
    try:
        res = client.rpc(
            "match_signals_hybrid",
            {
                "query_text": query_text,
                "query_embedding": query_embedding,
                "match_count": k,
                "full_text_weight": 1.0,
                "semantic_weight": 1.0,
            },
        ).execute()
        
        data = res.data or []
        out = []
        for row in data:
            meta = row.get("metadata", {}) if isinstance(row, dict) else {}
            item = dict(meta)
            item["similarity"] = round(float(row.get("similarity", 0.0)), 4)
            item["distance"] = round(1.0 - float(row.get("similarity", 0.0)), 4)
            item["content"] = row.get("document", "")
            item["rank_score"] = round(float(row.get("rank_score", 0.0)), 4)
            
            if "title" not in item:
                item["title"] = row.get("document", "")[:200]
            out.append(item)
        return out
    except Exception as e:
        logger.warning(f"pgvector hybrid query failed: {e}")
        return []
