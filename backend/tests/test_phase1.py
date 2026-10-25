"""Phase 1 tests: watchlist, briefs, history, PDF export."""
from unittest.mock import MagicMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)


def _mock_table(return_data=None):
    m = MagicMock()
    m.select.return_value.eq.return_value.order.return_value.execute.return_value.data = return_data or []
    m.select.return_value.eq.return_value.execute.return_value.data = return_data or []
    return m


def test_watchlist_get_empty_when_disabled():
    with patch("app.routes.watchlist.list_watchlist", return_value=[]):
        resp = client.get("/api/watchlist")
        assert resp.status_code == 200
        assert resp.json()["companies"] == []


def test_watchlist_add_and_delete():
    with patch("app.routes.watchlist.ensure_user", return_value=True), patch(
        "app.routes.watchlist.add_watchlist_company", return_value=True
    ), patch("app.routes.watchlist.list_watchlist", return_value=["TSMC"]), patch(
        "app.routes.watchlist.remove_watchlist_company", return_value=True
    ):
        resp = client.post("/api/watchlist", json={"company": "TSMC"})
        assert resp.status_code == 200
        assert "TSMC" in resp.json()["companies"]
        resp = client.delete("/api/watchlist/TSMC")
        assert resp.status_code == 200


def test_watchlist_alerts_matches_company():
    fake_events = [
        {"title": "TSMC N2 yield hits 90%", "content": "yield", "source": "Reuters", "timestamp": "2026-08-20T12:00:00Z", "company": "TSMC"},
        {"title": "Unrelated", "content": "nothing", "source": "X", "timestamp": "2026-08-20T12:00:00Z", "company": "Unknown"},
    ]
    with patch("app.routes.watchlist.list_watchlist", return_value=["TSMC"]), patch(
        "app.routes.watchlist.safe_read_jsonl", return_value=fake_events
    ):
        resp = client.get("/api/watchlist/alerts?limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["alerts"]) == 1
        assert data["alerts"][0]["matched_company"] == "TSMC"


def test_brief_share_and_public_read():
    with patch("app.routes.briefs.ensure_user", return_value=True), patch(
        "app.routes.briefs.is_supabase_enabled", return_value=True
    ), patch("app.routes.briefs.create_brief", return_value="brief-1"), patch(
        "app.core.tenant.get_brief",
        return_value={"id": "brief-1", "query_text": "TSMC?", "insight": "insight", "evidence": [], "is_public": True, "created_at": "2026-01-01"},
    ):
        resp = client.post("/api/briefs/share", json={"query": "TSMC?", "insight": "insight body", "evidence": []})
        assert resp.status_code == 200
        assert resp.json()["id"] == "brief-1"
        assert resp.json()["path"] == "/b/brief-1"
        resp = client.get("/api/briefs/public/brief-1")
        assert resp.status_code == 200
        assert resp.json()["query"] == "TSMC?"


def test_brief_share_unavailable_without_supabase():
    with patch("app.routes.briefs.is_supabase_enabled", return_value=False):
        resp = client.post("/api/briefs/share", json={"query": "q", "insight": "i", "evidence": []})
        assert resp.status_code == 503


def test_history_endpoints():
    with patch("app.routes.history.list_user_history", return_value=[{"id": "1", "query_text": "TSMC?", "created_at": "2026-01-01"}]):
        resp = client.get("/api/history/queries?limit=5")
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1
        resp = client.get("/api/history/insights?limit=5")
        assert resp.status_code == 200


def test_export_pdf_returns_pdf():
    resp = client.post(
        "/api/export",
        json={"query": "TSMC?", "report": "# Hello\nSome insight text.", "evidence": [{"title": "T", "snippet": "S", "source": "Reuters", "timestamp": "2026-01-01"}], "format": "pdf", "include_evidence": True},
    )
    assert resp.status_code == 200
    assert "application/pdf" in resp.headers.get("content-type", "")
    assert resp.content[:4] == b"%PDF"
