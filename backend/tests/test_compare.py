from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app
from app.models import EvidenceItem

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)


def _ev(title, company="TSMC", source="Reuters"):
    return EvidenceItem(title=title, snippet="snip", source=source, timestamp="2026-08-20T12:00:00Z", url="", company=company, event_type="supply_chain")


def test_compare_requires_two_companies():
    resp = client.post("/api/compare", json={"companies": ["TSMC"]})
    assert resp.status_code == 422


def test_compare_rejects_too_many():
    resp = client.post("/api/compare", json={"companies": ["A", "B", "C", "D", "E"]})
    assert resp.status_code == 422


def test_compare_success_with_mocked_retrieval():
    async def fake_retrieve(q, k=5, **kwargs):
        if "TSMC" in q:
            return [_ev("TSMC N2 yield hits 90%", "TSMC", "Reuters"), _ev("TSMC CoWoS expands", "TSMC", "Bloomberg")]
        return [_ev("NVIDIA Blackwell launch", "NVIDIA", "Reuters")]

    fake_report = '{"sections": [{"id": "evidence", "title": "Head-to-Head Evidence", "points": []}, {"id": "confidence", "title": "Confidence", "value": "Low", "reason": "Limited evidence"}, {"id": "ceo", "title": "Summary", "text": "Comparison based on retrieved evidence."}]}'
    with patch("app.routes.compare.retrieve_evidence", side_effect=fake_retrieve), patch(
        "app.routes.compare.embed_texts", new_callable=AsyncMock, return_value=[None, None]
    ), patch(
        "app.routes.compare.settings"
    ) as mock_settings, patch(
        "app.routes.compare.gemini_client.generate_content_with_fallback", new_callable=AsyncMock
    ) as mock_gen:
        mock_settings.gemini_api_key = "fake-key"
        mock_settings.gemini_model = "gemini-1.5-flash"
        mock_gen.return_value = fake_report
        resp = client.post("/api/compare", json={"companies": ["TSMC", "NVIDIA"], "k": 5})
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["companies"]) == 2
        assert data["companies"][0]["company"] == "TSMC"
        assert data["companies"][0]["evidence_count"] == 2
        assert data["companies"][1]["evidence_count"] == 1
        assert "overlap" in data
        assert "comparison_report" in data
        mock_gen.assert_called_once()


def test_compare_simulated_without_key():
    async def fake_retrieve(q, k=5, **kwargs):
        return [_ev("Some signal")]

    with patch("app.routes.compare.retrieve_evidence", side_effect=fake_retrieve), patch(
        "app.routes.compare.embed_texts", new_callable=AsyncMock, return_value=[None, None]
    ), patch(
        "app.routes.compare.settings"
    ) as mock_settings:
        mock_settings.gemini_api_key = ""
        mock_settings.gemini_model = "gemini-1.5-flash"
        resp = client.post("/api/compare", json={"companies": ["TSMC", "Intel"]})
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "simulated"
        assert "Comparison Evidence" in data["comparison_report"]
