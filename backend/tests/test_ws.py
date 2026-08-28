"""
WebSocket tests for /api/ws/signals.
Uses FastAPI TestClient websocket_connect. Auth is mocked by patching _verify_ws_token.
"""
import json
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.settings import settings

client = TestClient(app)


def test_ws_rejects_without_token():
    with pytest.raises(WebSocketDisconnect):
        with client.websocket_connect("/api/ws/signals") as ws:
            ws.receive_json()


def test_ws_rejects_bad_token():
    with patch("app.ws._verify_ws_token", return_value=None):
        with pytest.raises(WebSocketDisconnect):
            with client.websocket_connect("/api/ws/signals?token=bad") as ws:
                ws.receive_json()


def test_ws_sends_signals_and_pong(tmp_path):
    # Seed a temp stream file
    data_path = tmp_path / "stream.jsonl"
    events = [
        {"title": "WS Test Event A", "content": "content a", "timestamp": "2026-08-26T12:00:00Z", "source": "T", "company": "NVIDIA", "event_type": "general", "url": ""},
        {"title": "WS Test Event B", "content": "content b", "timestamp": "2026-08-26T11:00:00Z", "source": "T", "company": "TSMC", "event_type": "general", "url": ""},
    ]
    with open(data_path, "w", encoding="utf-8") as f:
        for e in events:
            f.write(json.dumps(e) + "\n")

    with patch("app.ws.safe_read_jsonl", return_value=events), \
         patch("app.ws.settings") as mock_settings, \
         patch("app.ws._verify_ws_token", return_value="user_ws_test"):
        mock_settings.resolved_data_path = data_path
        mock_settings.freshness_hours = 12
        mock_settings.clerk_issuer = settings.clerk_issuer
        mock_settings.clerk_audience = settings.clerk_audience

        with client.websocket_connect("/api/ws/signals?token=good") as ws:
            # First message: initial signals push
            msg = ws.receive_json()
            assert msg["type"] == "signals"
            assert msg["count"] == 2
            assert any(e["title"] == "WS Test Event A" for e in msg["events"])

            # Client ping -> pong
            ws.send_text("ping")
            pong = ws.receive_json()
            assert pong["type"] == "pong"

            # No change -> no push; ping again still works
            ws.send_text("ping")
            pong2 = ws.receive_json()
            assert pong2["type"] == "pong"



