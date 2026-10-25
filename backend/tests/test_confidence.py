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
    assert result["factors"]["corroboration"] == 0.5
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
