from app.services.near_duplicates import annotate_clusters, cluster_indices


def test_annotates_minor_headline_variants_and_keeps_unrelated_signals_separate():
    signals = [
        {"title": "TSMC expands advanced packaging capacity for AI chips", "snippet": "Taiwan production capacity grows."},
        {"title": "TSMC expands advanced packaging capacity for AI chips today", "snippet": "Taiwan production capacity grows."},
        {"title": "NVIDIA launches a new autonomous vehicle platform", "snippet": "The platform targets global automakers."},
    ]

    groups = annotate_clusters(signals)

    assert groups == [[0, 1], [2]]
    assert signals[0]["cluster_id"] == signals[1]["cluster_id"]
    assert signals[0]["cluster_size"] == signals[1]["cluster_size"] == 2
    assert signals[2]["cluster_size"] == 1


def test_empty_evidence_items_do_not_merge():
    groups = cluster_indices([{"title": ""}, {"title": ""}])
    assert groups == [[0], [1]]
