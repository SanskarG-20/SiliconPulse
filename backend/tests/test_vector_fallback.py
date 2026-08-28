"""
Fallback tests: pgvector → Chroma
"""
from unittest.mock import patch, MagicMock
from pathlib import Path


def test_vector_facade_prefers_pgvector_when_available():
    from app.services import vector_store as vs

    fake_events = [{"title": "TSMC", "content": "x", "source": "Reuters", "timestamp": "2026-08-20T12:00:00Z"}]
    fake_embs = [[0.1] * 768]

    with patch("app.services.vector_store._pg_available", return_value=True), \
         patch("app.services.vector_store._pg") as mock_pg:
        mock_pg.upsert_signals.return_value = 1
        mock_pg.query_similar.return_value = [{"title": "TSMC", "similarity": 0.9}]
        # Ensure Chroma not called
        with patch("app.services.vector_store._get_collection") as mock_coll:
            n = vs.upsert_signals(fake_events, fake_embs)
            assert n == 1
            mock_pg.upsert_signals.assert_called_once()
            mock_coll.assert_not_called()

            hits = vs.query_similar([0.1]*768, k=2)
            assert hits[0]["similarity"] == 0.9


def test_vector_facade_falls_back_to_chroma_on_pg_error():
    from app.services import vector_store as vs

    fake_events = [{"title": "TSMC", "content": "x", "source": "Reuters", "timestamp": "2026-08-20T12:00:00Z"}]
    fake_embs = [[0.1] * 768]

    mock_coll = MagicMock()
    mock_coll.upsert.return_value = None
    mock_coll.count.return_value = 1
    mock_coll.query.return_value = {
        "metadatas": [[{"title": "TSMC", "source": "Reuters"}]],
        "distances": [[0.1]],
        "documents": [["doc"]],
    }

    with patch("app.services.vector_store._pg_available", return_value=True), \
         patch("app.services.vector_store._pg") as mock_pg, \
         patch("app.services.vector_store._get_collection", return_value=mock_coll):
        mock_pg.upsert_signals.side_effect = Exception("pg down")
        n = vs.upsert_signals(fake_events, fake_embs)
        # Should fall back to Chroma and return 1
        assert n == 1
        mock_coll.upsert.assert_called_once()


def test_vector_count_fallback():
    from app.services import vector_store as vs

    with patch("app.services.vector_store._pg_available", return_value=False), \
         patch("app.services.vector_store._get_collection", return_value=None):
        assert vs.count() == 0
        assert vs.is_available() is False
