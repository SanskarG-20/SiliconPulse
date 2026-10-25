import sqlite3

from app.services import indexed_retrieval


def test_local_search_uses_fts_index_and_returns_matching_signal(monkeypatch, tmp_path):
    connection = sqlite3.connect(":memory:")
    monkeypatch.setattr(indexed_retrieval, "_connection", lambda: connection)
    events = [
        {"title": "TSMC expands advanced packaging capacity", "content": "Capacity will support AI chips.", "source": "Reuters", "url": "https://reuters.com/tsmc"},
        {"title": "NVIDIA launches autonomous vehicle platform", "content": "Automakers will use the platform.", "source": "AP", "url": "https://apnews.com/auto"},
    ]
    indexed_retrieval.index_local_events(events)

    results = indexed_retrieval.search_local_signals("TSMC packaging", tmp_path / "missing.jsonl")

    assert results is not None
    assert len(results) == 1
    assert results[0]["title"] == "TSMC expands advanced packaging capacity"
    assert results[0]["keyword_rank"] == 1
    connection.close()


def test_reciprocal_rank_fusion_and_reranker_merge_keyword_and_vector_hits():
    keyword = [{"event_id": "a", "title": "NVIDIA Taiwan chip supply", "source": "Reuters"}]
    vector = [
        {"event_id": "b", "title": "Unrelated market update", "similarity": 0.99},
        {"event_id": "a", "title": "NVIDIA Taiwan chip supply", "similarity": 0.75},
    ]

    fused = indexed_retrieval.reciprocal_rank_fusion(keyword, vector)
    ranked = indexed_retrieval.rerank_results("NVIDIA Taiwan chip supply", fused)

    assert len(fused) == 2
    assert fused[0]["event_id"] == "a"
    assert ranked[0]["event_id"] == "a"
    assert ranked[0]["rerank_score"] > ranked[1]["rerank_score"]
