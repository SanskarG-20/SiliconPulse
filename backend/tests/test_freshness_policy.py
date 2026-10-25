from datetime import datetime, timedelta, timezone

from app.services.freshness_policy import (
    filter_by_freshness,
    freshness_window_hours,
    is_within_window,
    query_intent,
)


def test_adaptive_windows_follow_query_intent_and_source_type():
    news = {"source": "Reuters", "event_type": "product launch"}
    official = {"source": "Official Press Release", "event_type": "launch"}
    filing = {"source": "SEC EDGAR", "event_type": "10-K filing"}

    assert query_intent("latest NVIDIA update") == "latest"
    assert query_intent("NVIDIA history and timeline") == "historical"
    assert freshness_window_hours("latest NVIDIA update", news, 12) == 12
    assert freshness_window_hours("latest NVIDIA update", official, 12) == 72
    assert freshness_window_hours("latest NVIDIA update", filing, 12) == 168
    assert freshness_window_hours("TSMC history", news) is None
    assert freshness_window_hours("TSMC news last week", news) == 168
    assert freshness_window_hours("TSMC news last month", news) == 720
    assert freshness_window_hours("NVIDIA overview", filing) is None


def test_freshness_filters_stale_items_and_marks_empty_window_fallbacks():
    now = datetime.now(timezone.utc)
    recent = {"title": "Recent news", "source": "Reuters", "timestamp": now.isoformat()}
    stale = {"title": "Older news", "source": "Reuters", "timestamp": (now - timedelta(days=10)).isoformat()}

    assert is_within_window(recent["timestamp"], 12, now)
    assert not is_within_window(stale["timestamp"], 12, now)
    assert filter_by_freshness("latest news", [recent, stale]) == [recent]
    assert filter_by_freshness("news about supply chain", [stale]) == [stale]
    assert filter_by_freshness("latest news", [stale])[0]["freshness_status"] == "outside_window_fallback"
    assert filter_by_freshness("supply chain history", [stale]) == [stale]
