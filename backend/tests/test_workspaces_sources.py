from unittest.mock import patch

from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)


def test_workspaces_list_empty():
    with patch("app.routes.workspaces.list_workspaces", return_value=[]):
        resp = client.get("/api/workspaces")
        assert resp.status_code == 200
        assert resp.json()["workspaces"] == []


def test_workspaces_create():
    ws = {"id": "w1", "name": "Fab Team", "invite_code": "abcd1234"}
    with patch("app.routes.workspaces.ensure_user", return_value=True), patch(
        "app.routes.workspaces.is_supabase_enabled", return_value=True
    ), patch("app.routes.workspaces.create_workspace", return_value=ws):
        resp = client.post("/api/workspaces", json={"name": "Fab Team"})
        assert resp.status_code == 200
        assert resp.json()["workspace"]["id"] == "w1"


def test_workspaces_create_unavailable_without_supabase():
    with patch("app.routes.workspaces.is_supabase_enabled", return_value=False):
        assert client.post("/api/workspaces", json={"name": "X"}).status_code == 503


def test_workspaces_join_invalid_code():
    with patch("app.routes.workspaces.ensure_user", return_value=True), patch(
        "app.routes.workspaces.is_supabase_enabled", return_value=True
    ), patch("app.routes.workspaces.join_workspace", return_value=None):
        assert client.post("/api/workspaces/join", json={"invite_code": "nope"}).status_code == 404


def test_workspaces_forbidden_for_non_member():
    with patch("app.core.tenant.is_workspace_member", return_value=False):
        assert client.get("/api/workspaces/w1").status_code == 403


def test_workspaces_detail_and_watchlist():
    with patch("app.core.tenant.is_workspace_member", return_value=True), patch(
        "app.routes.workspaces.list_workspace_members", return_value=[{"user_id": "test_user", "role": "owner"}]
    ), patch("app.routes.workspaces.list_workspace_watchlist", return_value=["TSMC"]), patch(
        "app.routes.workspaces.list_workspace_briefs", return_value=[]
    ), patch(
        "app.routes.workspaces.add_workspace_company", return_value=True
    ):
        resp = client.get("/api/workspaces/w1")
        assert resp.status_code == 200
        assert resp.json()["watchlist"] == ["TSMC"]
        resp = client.post("/api/workspaces/w1/watchlist", json={"company": "NVIDIA"})
        assert resp.status_code == 200


def test_rss_crud_and_validation():
    feeds = [{"id": "f1", "url": "https://example.com/feed.xml", "label": "Semi", "enabled": True}]
    with patch("app.routes.rss.ensure_user", return_value=True), patch(
        "app.routes.rss.is_supabase_enabled", return_value=True
    ), patch("app.routes.rss.add_rss_feed", return_value=feeds[0]), patch(
        "app.routes.rss.list_rss_feeds", return_value=feeds
    ):
        resp = client.post("/api/rss", json={"url": "https://example.com/feed.xml", "label": "Semi"})
        assert resp.status_code == 200
        assert resp.json()["feeds"][0]["id"] == "f1"
    # Non-http URL rejected
    assert client.post("/api/rss", json={"url": "ftp://example.com/x"}).status_code == 400


def test_rss_xml_parsing():
    from app.sources.rss_source import parse_feed_xml

    rss = """<?xml version="1.0"?><rss version="2.0"><channel><title>T</title>
    <item><title>TSMC N2 yield</title><link>https://e.com/1</link><description>Yield up</description><pubDate>Mon, 01 Sep 2026 12:00:00 GMT</pubDate></item>
    <item><title>Bad item</title></item></channel></rss>"""
    items = parse_feed_xml(rss)
    assert len(items) == 2
    assert items[0]["title"] == "TSMC N2 yield"

    atom = """<feed xmlns="http://www.w3.org/2005/Atom"><entry><title>NVIDIA launch</title>
    <link href="https://e.com/2"/><summary>GPU news</summary><updated>2026-09-01T12:00:00Z</updated></entry></feed>"""
    items = parse_feed_xml(atom)
    assert len(items) == 1
    assert items[0]["url"] == "https://e.com/2"
    assert parse_feed_xml("not xml <<<") == []


def test_edgar_url_and_pull():
    from app.sources import edgar_source as ed

    url = ed._filing_url("0001045810", "0001045810-20-000187", "0001045810-20-000187:q3fy21pr.htm")
    assert url == "https://www.sec.gov/Archives/edgar/data/1045810/000104581020000187/q3fy21pr.htm"
    assert ed._filing_url("", "", "") == ""
    assert ed._ticker_from_display(["NVIDIA CORP  (NVDA)  (CIK 0001045810)"]) == "NVDA"
    assert ed._ticker_from_display([]) is None

    fake_json = {"hits": {"hits": [{"_id": "0001045810-20-000187:q3fy21pr.htm", "_source": {
        "ciks": ["0001045810"], "form": "8-K", "file_date": "2026-09-01",
        "display_names": ["NVIDIA CORP  (NVDA)  (CIK 0001045810)"],
        "file_description": "Q3FY21 PRESS RELEASE", "adsh": "0001045810-20-000187", "items": ["2.02"],
    }}]}}

    class FakeResp:
        def raise_for_status(self):
            pass

        def json(self):
            return fake_json

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def get(self, *a, **k):
            return FakeResp()

    with patch("app.sources.edgar_source.httpx.Client", return_value=FakeClient()), patch(
        "app.sources.edgar_source.deduplicate_and_append", return_value=1
    ) as mock_dedup:
        added = ed.pull_edgar_signals(days_back=7)
        assert added >= 1
        events = mock_dedup.call_args[0][0]
        assert events[0]["company"] == "NVIDIA"
        assert events[0]["source"] == "EDGAR"
        assert "sec.gov/Archives" in events[0]["url"]
