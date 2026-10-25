import json

from app.models import InsightReport
from app.services.gemini_client import _provider_response_schema
from app.services.secure_prompt import ground_insight_report, validate_insight_report


EVIDENCE_CONTEXT = """[2026-10-25T10:00:00Z | Reuters] NVIDIA supply allocation expands
Company: NVIDIA | Event: supply_chain
Snippet: TSMC said it doubled HBM allocation for NVIDIA to support demand.
"""


def _report(span: str = "TSMC said it doubled HBM allocation for NVIDIA") -> InsightReport:
    return validate_insight_report(
        json.dumps({
            "sections": [
                {"id": "evidence", "title": "Evidence"},
                {
                    "id": "impact",
                    "title": "Supply impact",
                    "points": [
                        "NVIDIA doubled its HBM allocation at TSMC.",
                        "NVIDIA acquired Intel for $30 billion.",
                    ],
                    "text": "NVIDIA supply doubled. The company acquired Intel last night.",
                    "evidence": [{
                        "source": "Reuters",
                        "timestamp": "2026-10-25T10:00:00Z",
                        "title": "NVIDIA supply allocation expands",
                        "span": span,
                    }],
                },
                {"id": "confidence", "title": "Confidence", "value": "Medium", "reason": "Three sources."},
                {"id": "ceo", "title": "Summary", "text": "NVIDIA doubled HBM allocation."},
            ]
        })
    )


def test_grounding_keeps_only_claims_supported_by_exact_cited_spans():
    grounded, omitted = ground_insight_report(_report(), EVIDENCE_CONTEXT)

    impact = next(section for section in grounded.sections if section.id == "impact")
    assert impact.points == ["NVIDIA doubled its HBM allocation at TSMC."]
    assert impact.text == "NVIDIA supply doubled."
    assert impact.evidence[0].span == "TSMC said it doubled HBM allocation for NVIDIA"
    assert omitted == 4
    confidence = next(section for section in grounded.sections if section.id == "confidence")
    assert "4 unsupported claim(s) were omitted" in confidence.reason


def test_grounding_drops_claims_when_span_is_not_exactly_present():
    grounded, omitted = ground_insight_report(_report("NVIDIA has 100% of the market"), EVIDENCE_CONTEXT)
    impact = next(section for section in grounded.sections if section.id == "impact")
    assert impact.points == []
    assert impact.text is None
    assert impact.evidence is None
    assert omitted == 6


def test_gemini_schema_strips_unsupported_additional_properties_recursively():
    schema = _provider_response_schema(InsightReport)

    def contains_additional_properties(value):
        if isinstance(value, dict):
            return "additionalProperties" in value or any(contains_additional_properties(item) for item in value.values())
        if isinstance(value, list):
            return any(contains_additional_properties(item) for item in value)
        return False

    assert schema["type"] == "object"
    assert not contains_additional_properties(schema)
