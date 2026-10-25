"""Idempotently import local JSONL, SQLite checkpoints, and Chroma vectors to Supabase."""
from __future__ import annotations

import argparse
import json
import logging
import sqlite3
from pathlib import Path

from .services.signal_store import insert_events, is_enabled, set_checkpoint
from .settings import settings
from .supabase_client import get_supabase_client

logger = logging.getLogger(__name__)
BATCH_SIZE = 100


def _event_batches(path: Path):
    batch: list[dict] = []
    if not path.exists():
        return
    with path.open(encoding="utf-8", errors="replace") as source:
        for line_number, line in enumerate(source, 1):
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                logger.warning("Skipping malformed JSONL row %s:%s", path, line_number)
                continue
            if not isinstance(event, dict) or not str(event.get("title") or "").strip():
                continue
            batch.append(event)
            if len(batch) >= BATCH_SIZE:
                yield batch
                batch = []
    if batch:
        yield batch


def _read_checkpoints(path: Path) -> list[tuple[str, str]]:
    if not path.exists():
        return []
    try:
        conn = sqlite3.connect(str(path))
        try:
            return [
                (str(row[0]), str(row[1]))
                for row in conn.execute(
                    "SELECT source, last_checkpoint FROM source_checkpoints WHERE last_checkpoint IS NOT NULL"
                )
            ]
        finally:
            conn.close()
    except sqlite3.Error as exc:
        logger.warning("Could not read SQLite source checkpoints: %s", exc)
        return []


def _import_chroma(path: Path, dry_run: bool) -> tuple[int, int]:
    if not path.exists():
        return 0, 0
    try:
        import chromadb

        chroma = chromadb.PersistentClient(path=str(path))
        collection = chroma.get_collection("signals")
        total = collection.count()
    except Exception as exc:
        logger.warning("Could not read Chroma collection at %s: %s", path, exc)
        return 0, 0
    if dry_run:
        return total, 0
    client = get_supabase_client()
    if client is None:
        raise RuntimeError("Supabase client is unavailable")
    imported = 0
    for offset in range(0, total, BATCH_SIZE):
        data = collection.get(
            limit=BATCH_SIZE,
            offset=offset,
            include=["embeddings", "documents", "metadatas"],
        )
        ids = data.get("ids") or []
        embeddings = data.get("embeddings")
        if embeddings is None:
            continue
        documents = data.get("documents") or []
        metadatas = data.get("metadatas") or []
        rows = []
        for index, vector in enumerate(embeddings):
            rows.append({
                "id": ids[index],
                "embedding": vector.tolist() if hasattr(vector, "tolist") else list(vector),
                "document": documents[index] if index < len(documents) else "",
                "metadata": metadatas[index] if index < len(metadatas) and metadatas[index] else {},
            })
        client.table("signals_vec").upsert(rows, on_conflict="id").execute()
        imported += len(rows)
    return total, imported


def migrate(jsonl_path: Path, sqlite_path: Path, chroma_path: Path, dry_run: bool = False) -> dict:
    if not is_enabled() and not dry_run:
        raise RuntimeError("Configure SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY before migration")
    if not dry_run:
        # Confirms migration 008 and pgvector have been applied before importing.
        from .services.signal_store import check_ready

        check_ready()

    event_rows = sum(len(batch) for batch in _event_batches(jsonl_path))
    checkpoints = _read_checkpoints(sqlite_path)
    vector_rows, vector_imported = _import_chroma(chroma_path, dry_run)
    events_imported = 0
    if not dry_run:
        for batch in _event_batches(jsonl_path):
            events_imported += len(insert_events(batch))
        for source, checkpoint in checkpoints:
            set_checkpoint(source, checkpoint)
    return {
        "dry_run": dry_run,
        "jsonl_events_found": event_rows,
        "jsonl_events_imported": events_imported,
        "checkpoints_found": len(checkpoints),
        "chroma_vectors_found": vector_rows,
        "chroma_vectors_imported": vector_imported,
        "expired_websocket_tickets_imported": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jsonl", type=Path, default=settings.resolved_data_path)
    parser.add_argument("--sqlite", type=Path, default=Path(settings.db_path))
    parser.add_argument("--chroma", type=Path, default=Path(settings.db_path).parent / "chroma")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    print(json.dumps(migrate(args.jsonl, args.sqlite, args.chroma, args.dry_run), indent=2))


if __name__ == "__main__":
    main()
