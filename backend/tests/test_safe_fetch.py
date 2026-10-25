from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from app.services.safe_fetch import SafeFetchError, _resolve_public, safe_fetch


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "fc00::1"])
def test_resolver_rejects_non_public_addresses(monkeypatch, address):
    monkeypatch.setattr("socket.getaddrinfo", lambda *a, **k: [(2, 1, 6, "", (address, 443))])
    with pytest.raises(SafeFetchError):
        import asyncio

        asyncio.run(_resolve_public("attacker.example", 443))


class FakeResponse:
    def __init__(self, status=200, headers=None, chunks=(b"ok",)):
        self.status_code = status
        self.headers = headers or {"content-type": "application/rss+xml"}
        self._chunks = chunks

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError("http error")

    async def aiter_bytes(self):
        for chunk in self._chunks:
            yield chunk


class FakeClient:
    outcomes = []
    requested = []
    options = []

    def __init__(self, *args, **kwargs):
        self.options.append(kwargs)

    async def __aenter__(self):
        return self

    async def __aexit__(self, *args):
        return False

    @asynccontextmanager
    async def stream(self, method, url, **kwargs):
        self.requested.append((method, url, kwargs))
        outcome = self.outcomes.pop(0)
        yield outcome


@pytest.mark.asyncio
async def test_redirect_is_resolved_and_pinned_again(monkeypatch):
    FakeClient.outcomes = [
        FakeResponse(302, {"location": "https://next.example/feed", "content-type": "text/plain"}),
        FakeResponse(chunks=(b"feed",)),
    ]
    FakeClient.requested = []
    with patch("app.services.safe_fetch.httpx.AsyncClient", FakeClient), patch(
        "app.services.safe_fetch._resolve_public", new_callable=AsyncMock,
        side_effect=[["8.8.8.8"], ["1.1.1.1"]],
    ) as resolve:
        result = await safe_fetch("https://first.example/feed")
    assert result == b"feed"
    assert resolve.await_count == 2
    assert "8.8.8.8" in FakeClient.requested[0][1]
    assert "1.1.1.1" in FakeClient.requested[1][1]


@pytest.mark.asyncio
async def test_response_content_type_is_limited():
    FakeClient.outcomes = [FakeResponse(headers={"content-type": "text/html"})]
    with patch("app.services.safe_fetch.httpx.AsyncClient", FakeClient), patch(
        "app.services.safe_fetch._resolve_public", new_callable=AsyncMock, return_value=["8.8.8.8"]
    ), pytest.raises(SafeFetchError, match="content type"):
        await safe_fetch("https://feeds.example/feed")


@pytest.mark.asyncio
async def test_fetch_enforces_timeout_setting():
    from app.services.safe_fetch import DEFAULT_TIMEOUT

    FakeClient.outcomes = [FakeResponse(chunks=(b"feed",))]
    FakeClient.options = []
    with patch("app.services.safe_fetch.httpx.AsyncClient", FakeClient), patch(
        "app.services.safe_fetch._resolve_public", new_callable=AsyncMock, return_value=["8.8.8.8"]
    ):
        await safe_fetch("https://feeds.example/feed")
    assert FakeClient.options[0]["timeout"] == DEFAULT_TIMEOUT
    assert DEFAULT_TIMEOUT.connect == 3.0


@pytest.mark.asyncio
async def test_response_size_is_limited_while_streaming():
    FakeClient.outcomes = [FakeResponse(chunks=(b"1234", b"5678"))]
    with patch("app.services.safe_fetch.httpx.AsyncClient", FakeClient), patch(
        "app.services.safe_fetch._resolve_public", new_callable=AsyncMock, return_value=["8.8.8.8"]
    ), pytest.raises(SafeFetchError, match="maximum size"):
        await safe_fetch("https://feeds.example/feed", max_bytes=5)


@pytest.mark.asyncio
async def test_redirect_to_private_destination_is_rejected_before_second_request():
    FakeClient.outcomes = [FakeResponse(302, {"location": "http://127.0.0.1/latest/meta-data", "content-type": "text/plain"})]
    FakeClient.requested = []
    with patch("app.services.safe_fetch.httpx.AsyncClient", FakeClient), patch(
        "app.services.safe_fetch._resolve_public", new_callable=AsyncMock,
        side_effect=[["8.8.8.8"], SafeFetchError("private destination")],
    ) as resolve, pytest.raises(SafeFetchError):
        await safe_fetch("https://feeds.example/start")
    assert resolve.await_count == 2
    assert len(FakeClient.requested) == 1
