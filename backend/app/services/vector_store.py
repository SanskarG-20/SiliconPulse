"""
Vector store facade for SiliconPulse signals.
Tries Supabase pgvector first (persistent, shared), falls back to Chroma (local file).
Graceful no-op when both unavailable.
"""
from __future__ import annotations

import logging
import threading
from pathlib import Path

from app.settings import settings

logger = logging.getLogger(__name__)

# Try pgvector first
try:
    from . import pgvector_store as _pg  # type: ignore

    _PG_AVAILABLE = None  # lazy check
except ImportError:
    _pg = None  # type: ignore
    _PG_AVAILABLE = False

_collection = None
_lock = threading.Lock()
_available: bool | None = None


def _reset_collection():
    global _collection, _available
    with _lock:
        try:
            import chromadb

            path = str(Path(settings.db_path).parent / "chroma")
            client = chromadb.PersistentClient(path=path)
            try:
                client.delete_collection(name="signals")
                logger.warning("Chroma collection deleted due to dimension mismatch, recreating")
            except Exception:
                pass
            _collection = client.get_or_create_collection(
                name="signals",
                metadata={"hnsw:space": "cosine"},
            )
            _available = True
            logger.info(f"Chroma collection recreated at {path} ({_collection.count()} vectors)")
            return _collection
        except Exception as e:
            logger.warning(f"Chroma reset failed: {e}")
            _available = False
            _collection = None
            return None


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


def _pg_available() -> bool:
    global _PG_AVAILABLE
    if _PG_AVAILABLE is not None:
        return bool(_PG_AVAILABLE)
    if _pg is None:
        _PG_AVAILABLE = False
        return False
    try:
        ok = _pg.is_available()
        _PG_AVAILABLE = ok
        return ok
    except Exception:
        _PG_AVAILABLE = False
        return False


def is_available() -> bool:
    if _pg_available():
        return True
    return _get_collection() is not None


def upsert_signals(events: list[dict], embeddings: list[list[float]]) -> int:
    """Upsert events with embeddings. Returns count added. Tries pgvector first, then Chroma."""
    if not events or not embeddings:
        return 0
    # Try pgvector
    if _pg_available():
        try:
            n = _pg.upsert_signals(events, embeddings)
            if n:
                return n
        except Exception as e:
            logger.debug(f"pgvector upsert failed, falling back to Chroma: {e}")
    coll = _get_collection()
    if coll is None:
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
            try:
                coll.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=vecs)
            except Exception as e:
                if "dimension" in str(e).lower():
                    logger.warning(f"Chroma dimension mismatch ({e}), resetting collection")
                    coll = _reset_collection()
                    if coll is not None:
                        try:
                            coll.upsert(ids=ids, documents=docs, metadatas=metas, embeddings=vecs)
                        except Exception as e2:
                            logger.warning(f"Chroma upsert retry failed: {e2}")
                            return 0
                    else:
                        return 0
                else:
                    raise
            return len(ids)
    except Exception as e:
        logger.warning(f"Chroma upsert failed: {e}")
    return 0


def query_similar(query_embedding: list[float], k: int = 10) -> list[dict]:
    """
    Query similar signals. Returns list of dicts with metadata + distance + event payload.
    Tries pgvector first, then Chroma.
    """
    if not query_embedding:
        return []
    if _pg_available():
        try:
            res = _pg.query_similar(query_embedding, k=k)
            if res:
                return res
        except Exception as e:
            logger.debug(f"pgvector query failed, falling back: {e}")
    coll = _get_collection()
    if coll is None:
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
        if "dimension" in str(e).lower():
            logger.warning(f"Chroma query dimension mismatch ({e}), resetting collection")
            _reset_collection()
        else:
            logger.warning(f"Chroma query failed: {e}")
        return []


def count() -> int:
    if _pg_available():
        try:
            n = _pg.count()
            if n >= 0:
                return n
        except Exception:
            pass
    coll = _get_collection()
    if coll is None:
        return 0
    try:
        return coll.count()
    except Exception:
        return 0
