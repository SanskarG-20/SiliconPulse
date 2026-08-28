from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from app.query_cache import query_cache

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)


def _clear_query_cache():
    query_cache.clear()


def test_query_returns_evidence_and_signal():
    _clear_query_cache()
    with patch("app.routes.query.safe_read_jsonl") as mock_read:
        mock_read.return_value = [
            {
                "title": "NVIDIA launches H100 successor",
                "content": "NVIDIA unveils next-gen AI GPU with TSMC N3",
                "snippet": "NVIDIA unveils next-gen AI GPU",
                "source": "Reuters",
                "timestamp": "2026-08-20T12:00:00Z",
                "company": "NVIDIA",
                "event_type": "product_launch",
                "url": "https://example.com/nvidia",
            },
            {
                "title": "TSMC N2 yield hits 90%",
                "content": "TSMC reports N2 yield milestone",
                "snippet": "TSMC N2 yield",
                "source": "Bloomberg",
                "timestamp": "2026-08-20T11:00:00Z",
                "company": "TSMC",
                "event_type": "supply_chain",
                "url": "https://example.com/tsmc",
            },
        ]
        resp = client.post("/api/query", json={"query": "NVIDIA", "k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["query"] == "NVIDIA"
        assert len(data["evidence"]) >= 1
        assert "signal_strength" in data
        assert data["signal_strength"] >= 0
        assert "confidence" in data


def test_query_with_no_match_returns_empty():
    _clear_query_cache()
    with patch("app.routes.query.safe_read_jsonl") as mock_read:
        mock_read.return_value = [
            {
                "title": "Random unrelated title",
                "content": "nothing relevant here",
                "snippet": "nothing",
                "source": "Unknown",
                "timestamp": "2026-08-20T12:00:00Z",
                "company": "Unknown",
                "event_type": "general",
                "url": "",
            }
        ]
        resp = client.post("/api/query", json={"query": "zzzznonexistentzzz", "k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert data["evidence"] == []
        assert data["signal_strength"] == 0


def test_query_alias_expansion():
    _clear_query_cache()
    with patch("app.routes.query.safe_read_jsonl") as mock_read:
        mock_read.return_value = [
            {
                "title": "Jensen Huang keynote",
                "content": "NVIDIA CEO presents Blackwell",
                "snippet": "Jensen Huang keynote",
                "source": "MarketWire",
                "timestamp": "2026-08-20T12:00:00Z",
                "company": "NVIDIA",
                "event_type": "product_launch",
                "url": "",
            }
        ]
        # query via alias "jensen huang" should match via COMPANY_DICT
        resp = client.post("/api/query", json={"query": "jensen huang", "k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["evidence"]) >= 1


def test_generate_fallback_when_no_evidence():
    with patch("app.routes.query.safe_read_jsonl") as mock_read, patch("app.routes.query.settings") as mock_settings:
        mock_read.return_value = []
        mock_settings.gemini_api_key = "fake-key-for-test"
        mock_settings.gemini_model = "gemini-1.5-flash"
        # Need a valid path mock for the fallback branch that reads latest_events
        import tempfile
        from pathlib import Path

        with tempfile.TemporaryDirectory() as td:
            mock_settings.resolved_data_path = Path(td) / "stream.jsonl"
            resp = client.post("/api/generate", json={"query": "unknown query xyz", "context": ""})
            assert resp.status_code == 200
            data = resp.json()
            assert "insight" in data
            # fallback JSON contains Insufficient Live Signals when API key is present but no evidence
            assert "Insufficient Live Signals" in data["insight"] or "insufficient" in data["insight"].lower()


def test_generate_with_evidence_calls_gemini():
    fake_insight = '{"sections": [{"id": "evidence", "title": "Live Signal Evidence", "points": ["NVIDIA launched"]}]}'
    
    async def fake_stream(*args, **kwargs):
        yield fake_insight

    with patch("app.routes.query.gemini_client.generate_content_stream_with_fallback") as mock_gen:
        mock_gen.side_effect = fake_stream
        # need gemini_api_key set for this path
        with patch("app.routes.query.settings") as mock_settings:
            mock_settings.gemini_api_key = "fake-key"
            mock_settings.gemini_model = "gemini-1.5-flash"
            mock_settings.resolved_data_path = None  # not used when evidence_count>0
            context = "[2026-08-20T12:00:00Z | Reuters] NVIDIA launches H100 successor"
            resp = client.post("/api/generate", json={"query": "NVIDIA impact?", "context": context})
            assert resp.status_code == 200
            assert "sections" in resp.text
            mock_gen.assert_called_once()


def test_inject_then_query():
    _clear_query_cache()
    event = {"title": "Test Query Flow Unique 12345", "content": "Integration test content for query flow", "timestamp": "2026-08-20T12:00:00Z", "source": "TestSource", "company": "TestCo", "event_type": "general", "url": "https://example.com/test12345"}
    with patch("app.routes.query.safe_read_jsonl", return_value=[event]):
        resp = client.post("/api/query", json={"query": "Test Query Flow Unique 12345", "k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert any("Test Query Flow Unique 12345" in e["title"] for e in data["evidence"])


def test_radar_counts():
    with patch("app.routes.query.safe_read_jsonl") as mock_read:
        mock_read.return_value = [
            {"company": "NVIDIA", "title": "a", "timestamp": "2026-08-20T12:00:00Z"},
            {"company": "NVIDIA", "title": "b", "timestamp": "2026-08-20T12:00:00Z"},
            {"company": "TSMC", "title": "c", "timestamp": "2026-08-20T12:00:00Z"},
        ]
        resp = client.get("/api/radar")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        companies = [r["company"] for r in data]
        assert "NVIDIA" in companies


def test_export_md_includes_evidence():
    resp = client.post("/api/export", json={"query": "NVIDIA", "report": "# Test Report", "evidence": [{"title": "NVIDIA launch", "snippet": "snip", "source": "Reuters", "timestamp": "2026-08-20T12:00:00Z"}], "format": "md", "include_evidence": True})
    assert resp.status_code == 200
    assert "SiliconPulse Intelligence Report" in resp.text
    assert "NVIDIA launch" in resp.text


def test_verify_sources_returns_trust_levels():
    with patch("app.routes.sources.safe_read_jsonl") as mock_read:
        mock_read.return_value = [
            {"title": "NVIDIA launches GPU", "content": "NVIDIA content", "source": "Reuters", "timestamp": "2026-08-20T12:00:00Z"},
            {"title": "Random", "content": "noise", "source": "UnknownBlog", "timestamp": "2026-08-20T12:00:00Z"},
        ]
        resp = client.get("/api/sources/verify?query=NVIDIA")
        assert resp.status_code == 200
        data = resp.json()
        assert "sources" in data
        assert len(data["sources"]) >= 1
        assert data["sources"][0]["trust_level"] in ["High", "Medium", "Low"]
