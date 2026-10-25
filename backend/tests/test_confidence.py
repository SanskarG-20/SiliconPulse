from datetime import datetime, timedelta, timezone

from app.utils import compute_confidence


def test_confidence_breakdown_uses_independent_hosts_trust_recency_and_corroboration():
    recent = datetime.now(timezone.utc).isoformat()
    evidence = [
        {"source": "Reuters", "url": "https://www.reuters.com/a", "title": "TSMC expands HBM capacity", "timestamp": recent},
        {"source": "Reuters", "url": "https://reuters.com/b", "title": "TSMC expands HBM capacity", "timestamp": recent},
        {"source": "Bloomberg", "url": "https://www.bloomberg.com/a", "title": "TSMC expands HBM capacity", "timestamp": recent},
        {"source": "TechCrunch", "url": "https://techcrunch.com/a", "title": "NVIDIA signs new cloud deal", "timestamp": recent},
    ]

    result = compute_confidence(evidence)

    assert result["formula"].startswith("round(100 * (")
    assert result["factors"]["independent_source_count"] == 3
    assert result["factors"]["independent_source_factor"] == 1
    assert result["factors"]["source_trust"] == 0.8833
    assert result["factors"]["corroboration"] == 0.75
    assert result["factors"]["largest_cluster_size"] == 3
    assert result["factors"]["corroborated_cluster_count"] == 1
    assert result["factors"]["recency"] > 0.99
    assert 0 <= result["score"] <= 100


def test_confidence_decays_with_age_and_empty_evidence_is_zero():
    recent = {"source": "Reuters", "url": "https://reuters.com/a", "title": "NVIDIA supply update", "timestamp": datetime.now(timezone.utc).isoformat()}
    stale = dict(recent, timestamp=(datetime.now(timezone.utc) - timedelta(days=5)).isoformat())

    assert compute_confidence([recent])["factors"]["recency"] > compute_confidence([stale])["factors"]["recency"]
    empty = compute_confidence([])
    assert empty["score"] == 0
    assert empty["factors"]["independent_source_count"] == 0
    assert empty["factors"]["corroboration"] == 0


def test_near_duplicate_clusters_require_independent_sources_for_corroboration():
    title = "TSMC expands advanced packaging capacity for AI chips"
    evidence = [
        {"source": "Reuters", "url": "https://reuters.com/a", "title": title, "snippet": "Capacity for advanced AI chip packaging expands."},
        {"source": "Bloomberg", "url": "https://bloomberg.com/a", "title": title + " today", "snippet": "Capacity for advanced AI chip packaging expands."},
        {"source": "Reuters", "url": "https://reuters.com/b", "title": title + " today", "snippet": "Capacity for advanced AI chip packaging expands."},
    ]

    result = compute_confidence(evidence)

    assert result["factors"]["near_duplicate_cluster_count"] == 1
    assert result["factors"]["largest_cluster_size"] == 3
    assert result["factors"]["near_duplicate_event_count"] == 3
    assert result["factors"]["corroborated_cluster_count"] == 1
    assert result["factors"]["corroboration"] == 1

    same_source = [dict(item, url=f"https://reuters.com/{index}") for index, item in enumerate(evidence[:2])]
    same_source_result = compute_confidence(same_source)
    assert same_source_result["factors"]["largest_cluster_size"] == 2
    assert same_source_result["factors"]["corroboration"] == 0
