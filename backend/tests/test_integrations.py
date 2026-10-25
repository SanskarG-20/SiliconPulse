from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)


def test_keys_list_empty():
    with patch("app.routes.keys.list_api_keys", return_value=[]):
        resp = client.get("/api/keys")
        assert resp.status_code == 200
        assert resp.json()["keys"] == []


def test_keys_create_returns_raw_once():
    with patch("app.routes.keys.ensure_user", return_value=True), patch(
        "app.routes.keys.is_supabase_enabled", return_value=True
    ), patch("app.routes.keys.create_api_key", return_value={"id": "k1", "name": "ci"}):
        resp = client.post("/api/keys", json={"name": "ci"})
        assert resp.status_code == 200
        data = resp.json()
        assert data["key"].startswith("sp_live_")
        assert "never shown again" in data["warning"]


def test_keys_create_persists_scope_and_expiry():
    from unittest.mock import ANY
    with patch("app.routes.keys.ensure_user", return_value=True), patch(
        "app.routes.keys.is_supabase_enabled", return_value=True
    ), patch("app.routes.keys.create_api_key", return_value={"id": "k1", "name": "ci"}) as create:
        resp = client.post("/api/keys", json={"name": "ci", "scopes": ["query:read"], "expires_in_days": 30})
    assert resp.status_code == 200
    assert resp.json()["scopes"] == ["query:read"]
    assert resp.json()["expires_at"]
    create.assert_called_once_with("test_user", "ci", ANY, ANY, ["query:read"], ANY)


def test_keys_reject_unknown_scope():
    resp = client.post("/api/keys", json={"scopes": ["keys:manage"]})
    assert resp.status_code == 422


def test_key_rotation_returns_new_key_once():
    with patch("app.routes.keys.is_supabase_enabled", return_value=True), patch(
        "app.routes.keys.rotate_api_key", return_value={"id": "k2", "name": "ci", "scopes": ["query:read"]}
    ) as rotate:
        resp = client.post("/api/keys/k1/rotate")
    assert resp.status_code == 200
    assert resp.json()["key"].startswith("sp_live_")
    assert resp.json()["scopes"] == ["query:read"]
    assert "never shown again" in resp.json()["warning"]
    assert rotate.call_args.args[0] == "test_user"


def test_keys_create_unavailable_without_supabase():
    with patch("app.routes.keys.is_supabase_enabled", return_value=False):
        resp = client.post("/api/keys", json={"name": "ci"})
        assert resp.status_code == 503


def test_keys_revoke():
    with patch("app.routes.keys.revoke_api_key", return_value=True), patch(
        "app.routes.keys.list_api_keys", return_value=[]
    ):
        resp = client.delete("/api/keys/k1")
        assert resp.status_code == 200
        assert resp.json()["revoked"] == "k1"


def test_supabase_revoke_scopes_update_to_owner():
    from app import supabase_client
    table = MagicMock()
    client_mock = MagicMock()
    client_mock.table.return_value = table
    with patch.object(supabase_client, "get_supabase_client", return_value=client_mock):
        assert supabase_client.revoke_api_key("owner-a", "key-1") is True
    table.update.assert_called_once_with({"revoked": True})
    update = table.update.return_value
    update.eq.assert_any_call("id", "key-1")
    update.eq.return_value.eq.assert_called_once_with("user_id", "owner-a")


def test_api_key_auth_fallback_valid():
    with patch("app.supabase_client.lookup_api_key", return_value={"id": "k1", "user_id": "bot-user", "revoked": False}), patch(
        "app.supabase_client.touch_api_key"
    ):
        from app.core.auth import _verify_api_key

        result = _verify_api_key("sp_live_" + "a" * 24)
        assert result["user_id"] == "bot-user"
        assert result["via"] == "api_key"


def test_api_key_auth_rejects_bad_key():
    with patch("app.supabase_client.lookup_api_key", return_value=None):
        from app.core.auth import _verify_api_key

        assert _verify_api_key("sp_live_" + "z" * 24) is None
        assert _verify_api_key("not-a-key") is None
        assert _verify_api_key("") is None


def test_api_key_auth_rejects_expired_or_malformed_expiry():
    from app.core.auth import _verify_api_key
    expired = {"id": "k1", "user_id": "u1", "expires_at": "2000-01-01T00:00:00Z"}
    invalid = {"id": "k1", "user_id": "u1", "expires_at": "not-a-date"}
    for row in (expired, invalid):
        with patch("app.supabase_client.lookup_api_key", return_value=row), patch("app.supabase_client.touch_api_key"):
            assert _verify_api_key("sp_live_" + "a" * 24) is None


def test_api_key_auth_returns_scopes():
    from app.core.auth import _verify_api_key
    row = {"id": "k1", "user_id": "u1", "scopes": ["query:read"]}
    with patch("app.supabase_client.lookup_api_key", return_value=row), patch("app.supabase_client.touch_api_key"):
        assert _verify_api_key("sp_live_" + "a" * 24)["scopes"] == ["query:read"]


def test_api_key_with_explicit_empty_scopes_stays_restricted():
    from app.core.auth import _verify_api_key
    row = {"id": "k1", "user_id": "u1", "scopes": []}
    with patch("app.supabase_client.lookup_api_key", return_value=row), patch("app.supabase_client.touch_api_key"):
        assert _verify_api_key("sp_live_" + "a" * 24)["scopes"] == []


def test_api_key_request_fails_closed_without_required_scope():
    from starlette.requests import Request
    from fastapi import HTTPException
    from app.core.auth import get_current_user

    scope = {"type": "http", "method": "POST", "path": "/api/generate", "headers": [(b"x-api-key", b"sp_live_test")], "query_string": b"", "server": ("test", 80), "scheme": "http", "client": ("test", 1)}
    with patch("app.core.auth._verify_api_key", return_value={"user_id": "u1", "scopes": ["query:read"]}):
        try:
            get_current_user(Request(scope), credentials=None)
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("missing reports:generate scope must fail closed")


def test_api_key_cannot_reach_unscoped_write_endpoints():
    from starlette.requests import Request
    from fastapi import HTTPException
    from app.core.auth import get_current_user

    scope = {"type": "http", "method": "POST", "path": "/api/webhooks", "headers": [(b"x-api-key", b"sp_live_test")], "query_string": b"", "server": ("test", 80), "scheme": "http", "client": ("test", 1)}
    with patch("app.core.auth._verify_api_key", return_value={"user_id": "u1", "scopes": ["signals:read", "query:read", "trends:read", "compare:read", "reports:generate"]}):
        try:
            get_current_user(Request(scope), credentials=None)
        except HTTPException as exc:
            assert exc.status_code == 403
        else:
            raise AssertionError("unknown/write endpoints must fail closed for API keys")


def test_webhooks_reject_non_slack_url():
    resp = client.post("/api/webhooks", json={"url": "https://evil.example.com/hook", "events": ["spike.alert"]})
    assert resp.status_code == 400


def test_webhooks_add_and_list():
    row = {"id": "w1", "url": "https://hooks.slack.com/x", "events": ["spike.alert"], "enabled": True}
    with patch("app.routes.webhooks.ensure_user", return_value=True), patch(
        "app.routes.webhooks.add_team_webhook", return_value=row
    ), patch("app.routes.webhooks.list_team_webhooks", return_value=[{**row, "url": "", "url_host": "hooks.slack.com"}]):
        resp = client.post("/api/webhooks", json={"url": "https://hooks.slack.com/services/T/B/X", "events": ["spike.alert"]})
        assert resp.status_code == 200
        assert resp.json()["webhooks"][0]["url_host"] == "hooks.slack.com"


def test_webhook_test_endpoint():
    with patch("app.routes.webhooks.send_slack", new_callable=AsyncMock) as mock_send:
        mock_send.return_value = True
        resp = client.post("/api/webhooks/test", json={"url": "https://hooks.slack.com/services/T/B/X"})
        assert resp.status_code == 200
        assert resp.json() == {"ok": True}


def test_spike_service_no_webhooks():
    with patch("app.supabase_client.list_enabled_spike_webhooks", return_value=[]):
        from app.services.webhook_service import run_spike_alerts_sync

        assert run_spike_alerts_sync() == {"checked": 0, "sent": 0, "spike": False}


def test_spike_service_sends_on_spike():
    from app.services import webhook_service as ws

    fake_hooks = [{"id": "w1", "url": "https://hooks.slack.com/x", "user_id": "u1"}]
    with patch("app.supabase_client.list_enabled_spike_webhooks", return_value=fake_hooks), patch.object(
        ws, "global_spike", return_value={"is_spike": True, "today": 9, "mean": 2.0, "std": 1.0, "top_companies": [{"company": "TSMC", "count": 5}], "date": "2026-09-06"}
    ), patch("app.services.webhook_service.send_slack", new_callable=AsyncMock) as mock_send, patch(
        "app.supabase_client.mark_webhook_sent"
    ):
        mock_send.return_value = True
        result = ws.run_spike_alerts_sync()
        assert result["sent"] == 1
        assert result["spike"] is True
