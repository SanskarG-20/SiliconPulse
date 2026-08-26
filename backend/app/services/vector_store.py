"""
Chroma vector store for SiliconPulse signals.
Persistent collection stored in data/chroma. Graceful no-op when unavailable.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from app.settings import settings

logger = logging.getLogger(__name__)

_collection = None
_lock = threading.Lock()
_available: bool | None = None


def _get_collection():
    global _collection, _available
    if _collection is not None:
        return _collection
    if _available is False:
        return None
    with _lock:
        if _collection is not None:
            return _collection
        try:
            import chromadb

            path = str(Path(settings.db_path).parent / "chroma")
            client = chromadb.PersistentClient(path=path)
            _collection = client.get_or_create_collection(
                name="signals",
                metadata={"hnsw:space": "cosine"},
            )
            _available = True
            logger.info(f"Chroma collection ready at {path} ({_collection.count()} vectors)")
        except Exception as e:
            logger.warning(f"Chroma unavailable, vector search disabled: {e}")
            _available = False
            _collection = None
    return _collection


def is_available() -> bool:
    return _get_collection() is not None


def upsert_signals(events: list[dict], embeddings: list[list[float]]) -> int:
    """Upsert events with embeddings. Returns count added."""
    coll = _get_collection()
    if coll is None or not events or not embeddings:
        return 0
    try:
        ids, docs, metas, vecs = [], [], [], []
        for ev, emb in zip(events, embeddings):
            if not emb:
                continue
            # stable id from title+source+url
            from app.utils import compute_event_id

            eid = compute_event_id(ev)
            ids.append(eid)
            docs.append(f"{ev.get('title','')} {ev.get('content') or ev.get('snippet','')}"[:2000])
            metas.append(
                {
                    "title": ev.get("title", "")[:500],
                    "source": ev.get("source", "Unknown")[:100],
                    "timestamp": ev.get("timestamp", ""),
                    "company": (ev.get("company") or "")[:100],
                    "event_type": (ev.get("event_type") or "general")[:50],
                    "url": (ev.get("url") or "")[:500],
                }
            )
            vecs.append(emb)
        if ids:
            coll.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=vecs)
            return len(ids)
    except Exception as e:
        logger.warning(f"Chroma upsert failed: {e}")
    return 0


def query_similar(query_embedding: list[float], k: int = 10) -> list[dict]:
    """
    Query similar signals. Returns list of dicts with metadata + distance + event payload.
    """
    coll = _get_collection()
    if coll is None or not query_embedding:
        return []
    try:
        res = coll.query(query_embeddings=[query_embedding], n_results=min(k, coll.count() or 1))
        metas = res.get("metadatas", [[]])[0]
        dists = res.get("distances", [[]])[0]
        docs = res.get("documents", [[]])[0]
        out = []
        for meta, dist, doc in zip(metas, dists, docs):
            item = dict(meta)
            item["distance"] = dist
            # cosine distance -> similarity 0..1
            item["similarity"] = round(max(0.0, 1.0 - float(dist)), 4)
            item["content"] = doc
            out.append(item)
        return out
    except Exception as e:
        logger.warning(f"Chroma query failed: {e}")
        return []


def count() -> int:
    coll = _get_collection()
    if coll is None:
        return 0
    try:
        return coll.count()
    except Exception:
        return 0
