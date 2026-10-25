from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)

PUBLIC_BRIEF = {"id": "b1", "query_text": "TSMC?", "insight": "i", "evidence": [], "is_public": True, "created_at": "2026-01-01"}


def test_comments_thread_public():
    with patch("app.core.tenant.get_brief", return_value=PUBLIC_BRIEF), patch(
        "app.routes.comments.list_brief_comments", return_value=[{"id": "c1", "user_id": "u1", "body": "Agreed", "created_at": "2026-01-02"}]
    ):
        resp = client.get("/api/briefs/public/b1/comments")
        assert resp.status_code == 200
        assert len(resp.json()["comments"]) == 1


def test_comments_thread_404_for_missing_brief():
    with patch("app.core.tenant.get_brief", return_value=None):
        assert client.get("/api/briefs/public/nope/comments").status_code == 404


def test_comments_thread_403_for_private_brief():
    with patch("app.core.tenant.get_brief", return_value={**PUBLIC_BRIEF, "is_public": False}):
        assert client.get("/api/briefs/public/b1/comments").status_code == 403


def test_post_comment():
    row = {"id": "c2", "body": "Check CoWoS capacity", "created_at": "2026-01-03"}
    with patch("app.core.tenant.get_brief", return_value=PUBLIC_BRIEF), patch(
        "app.routes.comments.ensure_user", return_value=True
    ), patch("app.routes.comments.add_brief_comment", return_value=row):
        resp = client.post("/api/briefs/b1/comments", json={"body": "Check CoWoS capacity"})
        assert resp.status_code == 200
        assert resp.json()["comment"]["id"] == "c2"


def test_post_comment_rejects_empty():
    with patch("app.core.tenant.get_brief", return_value=PUBLIC_BRIEF):
        assert client.post("/api/briefs/b1/comments", json={"body": "   "}).status_code in (400, 422)


def test_post_comment_unavailable_without_supabase():
    with patch("app.core.tenant.get_brief", return_value=PUBLIC_BRIEF), patch(
        "app.routes.comments.ensure_user", return_value=True
    ), patch("app.routes.comments.add_brief_comment", return_value=None), patch(
        "app.routes.comments.is_supabase_enabled", return_value=False
    ):
        assert client.post("/api/briefs/b1/comments", json={"body": "hi"}).status_code == 503


def test_delete_comment():
    with patch("app.routes.comments.delete_brief_comment", return_value=True):
        resp = client.delete("/api/comments/c2")
        assert resp.status_code == 200
        assert resp.json() == {"deleted": "c2"}
