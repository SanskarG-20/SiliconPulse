"""
Tests for vector search: embedding service + Chroma store + hybrid query.
All LLM/embedding calls are mocked; Chroma runs for real (local, fast).
"""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from app.query_cache import query_cache

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)

FAKE_VEC = [0.1] * 768


def _clear_query_cache():
    query_cache.clear()


def test_vector_store_available():
    from app.services.vector_store import count, is_available
    assert is_available() is True
    assert count() >= 0


def test_upsert_and_query_similar():
    from app.services.vector_store import count, query_similar, upsert_signals

    events = [
        {"title": "TSMC N2 yield milestone", "content": "TSMC reports 2nm yield", "source": "Reuters", "timestamp": "2026-08-20T12:00:00Z", "company": "TSMC", "event_type": "supply_chain", "url": "https://e.com/1"},
        {"title": "NVIDIA launches Blackwell", "content": "NVIDIA new GPU", "source": "Bloomberg", "timestamp": "2026-08-20T11:00:00Z", "company": "NVIDIA", "event_type": "product_launch", "url": "https://e.com/2"},
    ]
    embs = [[0.01 * (i + 1)] * 768 for i in range(2)]
    n = upsert_signals(events, embs)
    assert n == 2
    assert count() >= 2

    hits = query_similar([0.01] * 768, k=2)
    assert len(hits) >= 1
    assert "similarity" in hits[0]
    assert 0.0 <= hits[0]["similarity"] <= 1.0


def test_embedding_no_key_returns_none():
    from app.services import embedding_service as es

    with patch.object(es.settings, "gemini_api_key", ""):
        import asyncio
        res = asyncio.run(es.embed_text("hello"))
        assert res is None


def test_embedding_with_mock():
    from app.services import embedding_service as es

    class FakeEmb:
        def __init__(self, v):
            self.values = v

    class FakeResp:
        embeddings = [FakeEmb(FAKE_VEC)]

    class FakeModels:
        async def embed_content(self, model, contents):
            return FakeResp()

    class FakeAio:
        models = FakeModels()

    class FakeClient:
        aio = FakeAio()

    with patch.object(es.settings, "gemini_api_key", "fake"), patch("google.genai.Client", return_value=FakeClient()):
        import asyncio
        res = asyncio.run(es.embed_text("mocked text"))
        assert res == FAKE_VEC


def test_hybrid_query_vector_merge():
    _clear_query_cache()
    events = [
        # keyword-miss but semantically relevant (mocked embedding will match query)
        {"title": "Chipmaker output slows unexpectedly", "content": "foundry output reduction impacts GPU supply", "snippet": "foundry output reduction", "source": "Reuters", "timestamp": "2026-08-20T12:00:00Z", "company": "TSMC", "event_type": "supply_chain", "url": ""},
        # keyword-hit
        {"title": "NVIDIA GPU launch", "content": "NVIDIA GPU launch", "snippet": "NVIDIA GPU launch", "source": "Bloomberg", "timestamp": "2026-08-20T11:00:00Z", "company": "NVIDIA", "event_type": "product_launch", "url": ""},
    ]
    fake_hits = [
        {"title": events[0]["title"], "similarity": 0.91, "distance": 0.09, "content": events[0]["content"]},
    ]
    with patch("app.routes.query.safe_read_jsonl", return_value=events), \
         patch("app.routes.query.vector_available", return_value=True), \
         patch("app.routes.query.embed_text", new_callable=AsyncMock, return_value=FAKE_VEC), \
         patch("app.routes.query.query_similar", return_value=fake_hits):
        resp = client.post("/api/query", json={"query": "GPU supply problems", "k": 5})
        assert resp.status_code == 200
        data = resp.json()
        titles = [e["title"] for e in data["evidence"]]
        assert "NVIDIA GPU launch" in titles          # keyword path
        assert "Chipmaker output slows unexpectedly" in titles  # semantic merge path


def test_hybrid_query_no_vector_graceful():
    _clear_query_cache()
    events = [
        {"title": "NVIDIA GPU launch", "content": "NVIDIA GPU launch", "snippet": "x", "source": "B", "timestamp": "2026-08-20T11:00:00Z", "company": "NVIDIA", "event_type": "product_launch", "url": ""},
    ]
    with patch("app.routes.query.safe_read_jsonl", return_value=events), \
         patch("app.routes.query.vector_available", return_value=False):
        resp = client.post("/api/query", json={"query": "NVIDIA", "k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["evidence"]) >= 1  # keyword-only still works


def test_health_reports_vector():
    resp = client.get("/health")
    assert resp.status_code == 200
    checks = resp.json()["checks"]
    assert "vector_store" in checks


def test_metrics_reports_vector():
    resp = client.get("/metrics")
    assert resp.status_code == 200
    data = resp.json()
    assert "vector_signals" in data
    assert "embedding_cache_entries" in data
