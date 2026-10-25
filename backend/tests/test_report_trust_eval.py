from pathlib import Path

from evals.report_trust_eval import _gemini_schema, _load_golden, evaluate_case, summarize


def test_golden_benchmark_has_fifty_complete_cases():
    golden = Path(__file__).parents[1] / "evals" / "golden_queries.json"
    cases = _load_golden(golden)
    assert len(cases) == 50
    assert all(case["expected_entities"] and case["expected_source_domains"] and case["key_facts"] for case in cases)


def test_gemini_schema_removes_unsupported_keywords_recursively():
    schema = _gemini_schema({"additionalProperties": False, "items": {"additionalProperties": False, "type": "object"}})
    assert schema == {"items": {"type": "object"}}


def test_eval_reports_retrieval_recall_valid_citations_and_unsupported_claims():
    case = {
        "id": "test",
        "expected_entities": ["NVIDIA"],
        "expected_source_domains": ["example.com"],
        "key_facts": ["TSMC expanded advanced packaging capacity"],
    }
    evidence = [{
        "source": "Reuters",
        "timestamp": "2026-01-01T00:00:00Z",
        "title": "NVIDIA and TSMC expand capacity",
        "snippet": "NVIDIA said TSMC expanded advanced packaging capacity this quarter.",
        "url": "https://www.example.com/story",
    }]
    report = {"sections": [{
        "id": "impact",
        "points": [
            "NVIDIA said TSMC expanded advanced packaging capacity this quarter.",
            "The factory output doubled last month.",
        ],
        "evidence": [{"source": "Reuters", "timestamp": "2026-01-01T00:00:00Z", "title": "NVIDIA and TSMC expand capacity"}],
    }]}

    result = evaluate_case(case, evidence, report)

    assert result["recall_at_k"] == 1
    assert result["citation_accuracy"] == 1
    assert result["report_claim_count"] == 2
    assert result["unsupported_claim_count"] == 1
    assert result["hallucination_rate"] == 0.5
    assert summarize([result])["hallucination_rate"] == 0.5


def test_eval_marks_unresolved_citations_and_unsupported_claims():
    evidence = [{"source": "Reuters", "timestamp": "2026-01-01", "title": "NVIDIA capacity expands", "snippet": "NVIDIA expanded capacity.", "url": "https://reuters.com/a"}]
    report = {"sections": [{"id": "ceo", "text": "NVIDIA capacity expanded.", "evidence": [{"source": "Bloomberg", "timestamp": "2026-01-01", "title": "NVIDIA capacity expands"}]}]}

    result = evaluate_case({"id": "unresolved", "expected_entities": [], "expected_source_domains": [], "key_facts": []}, evidence, report)

    assert result["citation_accuracy"] == 0
    assert result["hallucination_rate"] == 1
