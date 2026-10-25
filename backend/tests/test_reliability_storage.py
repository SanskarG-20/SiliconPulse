import json
import sqlite3
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest


def test_canonical_ingestion_uses_postgres_and_does_not_write_jsonl(tmp_path, monkeypatch):
    from app.services import signal_store
    from app.settings import settings
    from app.utils import deduplicate_and_append

    event = {"title": "Canonical TSMC signal", "content": "Postgres owns this", "source": "Test"}
    target = tmp_path / "stream.jsonl"
    monkeypatch.setattr(signal_store, "is_enabled", lambda: True)
    monkeypatch.setattr(signal_store, "insert_events", lambda events: events)
    monkeypatch.setattr(settings, "local_cache_enabled", False)
    monkeypatch.setattr(settings, "redis_url", "")
    with patch("app.services.vector_store.is_available", return_value=False):
        assert deduplicate_and_append([event], target) == 1
    assert not target.exists()


def test_canonical_reader_ignores_stale_jsonl_cache(tmp_path, monkeypatch):
    from app.services import signal_store
    from app.utils import safe_read_jsonl

    cache = tmp_path / "stream.jsonl"
    cache.write_text(json.dumps({"title": "Stale local event"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(signal_store, "is_enabled", lambda: True)
    monkeypatch.setattr(
        signal_store,
        "list_events",
        lambda limit: [{"title": "Canonical database event", "timestamp": "2026-10-25T00:00:00Z"}],
    )
    events = safe_read_jsonl(cache, limit=1)
    assert [event["title"] for event in events] == ["Canonical database event"]


def test_signal_store_uses_atomic_postgres_insert_rpc(monkeypatch):
    from app.services import signal_store

    response = SimpleNamespace(data=[{"event_id": "new-id", "payload": {"title": "Inserted"}}])
    client = MagicMock()
    client.rpc.return_value.execute.return_value = response
    monkeypatch.setattr(signal_store, "get_supabase_client", lambda: client)
    events = [{"title": "Inserted", "source": "Test"}]
    assert signal_store.insert_events(events) == [{"title": "Inserted"}]
    name, params = client.rpc.call_args.args
    assert name == "ingest_market_signals"
    assert params["p_events"][0]["payload"] == events[0]
    assert params["p_events"][0]["event_id"]


def test_hosted_vector_outage_does_not_fall_back_to_chroma(monkeypatch):
    from app.services import vector_store

    monkeypatch.setattr(vector_store, "is_supabase_enabled", lambda: True)
    monkeypatch.setattr(vector_store, "_pg_available", lambda: False)
    with patch.object(vector_store, "_get_collection") as local_collection:
        assert vector_store.is_available() is False
        assert vector_store.upsert_signals([{"title": "signal"}], [[0.1] * 768]) == 0
        assert vector_store.query_similar([0.1] * 768) == []
        assert vector_store.count() == -1
        local_collection.assert_not_called()


def test_supabase_checkpoints_are_used_instead_of_sqlite(monkeypatch):
    from app import storage
    from app.services import signal_store
    from app.supabase_client import is_supabase_enabled

    monkeypatch.setattr("app.supabase_client.is_supabase_enabled", lambda: True)
    monkeypatch.setattr(signal_store, "get_checkpoint", lambda source: "2026-10-24T12:00:00Z")
    monkeypatch.setattr(signal_store, "set_checkpoint", MagicMock())
    with patch.object(storage, "get_db_connection", side_effect=AssertionError("SQLite should not be opened")):
        assert storage.get_checkpoint("GDELT") == "2026-10-24T12:00:00Z"
        storage.update_checkpoint("GDELT", "2026-10-25T12:00:00Z")
    signal_store.set_checkpoint.assert_called_once_with("GDELT", "2026-10-25T12:00:00Z")


def test_production_rejects_sqlite_fallback(monkeypatch, tmp_path):
    from app import storage
    from app.settings import settings

    monkeypatch.setattr(settings, "app_env", "production")
    monkeypatch.setattr("app.supabase_client.is_supabase_enabled", lambda: False)
    monkeypatch.setattr(settings, "db_path", str(tmp_path / "must-not-exist.sqlite"))
    with pytest.raises(RuntimeError, match="local-development fallback"):
        storage.get_db_connection()
    assert not (tmp_path / "must-not-exist.sqlite").exists()


def test_local_migration_is_idempotent_and_imports_checkpoints(tmp_path, monkeypatch):
    from app import migrate_local_storage as migration
    from app.services import signal_store

    source = tmp_path / "stream.jsonl"
    source.write_text(
        json.dumps({"title": "Event one", "source": "test"}) + "\n"
        + json.dumps({"title": "Event two", "source": "test"}) + "\n",
        encoding="utf-8",
    )
    db_path = tmp_path / "legacy.sqlite"
    conn = sqlite3.connect(str(db_path))
    conn.execute("CREATE TABLE source_checkpoints (source TEXT, last_checkpoint TEXT)")
    conn.execute("INSERT INTO source_checkpoints VALUES (?, ?)", ("GDELT", "2026-10-24T12:00:00Z"))
    conn.commit()
    conn.close()

    monkeypatch.setattr(migration, "is_enabled", lambda: True)
    monkeypatch.setattr(signal_store, "check_ready", lambda: None)
    monkeypatch.setattr(migration, "_import_chroma", lambda path, dry_run: (0, 0))
    monkeypatch.setattr(migration, "insert_events", MagicMock(side_effect=[[{"title": "Event one"}, {"title": "Event two"}], []]))
    monkeypatch.setattr(migration, "set_checkpoint", MagicMock())

    first = migration.migrate(source, db_path, tmp_path / "missing-chroma")
    second = migration.migrate(source, db_path, tmp_path / "missing-chroma")
    assert first["jsonl_events_imported"] == 2
    assert second["jsonl_events_imported"] == 0
    assert first["checkpoints_found"] == 1
    assert migration.set_checkpoint.call_count == 2


def test_migration_dry_run_does_not_require_supabase(tmp_path, monkeypatch):
    from app import migrate_local_storage as migration
    from app.services import signal_store

    path = tmp_path / "stream.jsonl"
    path.write_text(json.dumps({"title": "Review only"}) + "\n", encoding="utf-8")
    monkeypatch.setattr(migration, "is_enabled", lambda: False)
    monkeypatch.setattr(migration, "_import_chroma", lambda chroma, dry_run: (0, 0))
    report = migration.migrate(path, tmp_path / "missing.sqlite", tmp_path / "missing", dry_run=True)
    assert report["jsonl_events_found"] == 1
    assert report["jsonl_events_imported"] == 0


def test_pathway_integration_is_removed():
    from app.settings import settings

    assert not hasattr(settings, "use_pathway")
    assert not Path(__file__).parents[1].joinpath("pathway_pipeline.py").exists()
    assert "Pathway" not in Path(__file__).parents[2].joinpath("README.md").read_text(encoding="utf-8")
