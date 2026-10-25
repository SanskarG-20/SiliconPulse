"""Company / sector comparison (Phase 2.2). Reuses retrieval + graph engines."""
import json
import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from ..core.auth import get_current_user
from ..core.limiter import limiter
from ..graph.store import get_impact, get_suppliers
from ..retrieval import retrieve_evidence
from ..services.gemini_client import gemini_client
from ..services.secure_prompt import SYSTEM_INSTRUCTION_HIERARCHY, ground_insight_report, untrusted_block, validate_insight_report
from ..models import InsightReport
from ..settings import settings
from ..supabase_client import ensure_user
from ..utils import compute_confidence, extract_companies

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


class CompareRequest(BaseModel):
    companies: list[str] = Field(..., min_length=2, max_length=4, description="2-4 company names to compare")
    query: str = Field(default="", max_length=200, description="Optional shared context, e.g. 'N2 yield'")
    k: int = Field(default=5, ge=1, le=10, description="Evidence items per company")
    depth: int = Field(default=2, ge=1, le=3, description="Graph BFS depth")


def _summarize_evidence(evidence: list) -> dict:
    if not evidence:
        return {"count": 0, "latest_title": None, "latest_timestamp": None, "sources": []}
    latest = max(evidence, key=lambda e: str(e.timestamp or ""))
    sources = sorted({str(e.source or "Unknown") for e in evidence})
    return {
        "count": len(evidence),
        "latest_title": latest.title,
        "latest_timestamp": latest.timestamp,
        "sources": sources[:5],
    }


@router.post("/compare")
@limiter.limit("10/minute")
async def compare_companies(request: Request, body: CompareRequest, user=Depends(get_current_user)):
    """Side-by-side comparison across 2-4 companies with graph overlap + LLM verdict."""
    # Normalize + validate company names
    seen_lower = set()
    companies: list[str] = []
    for raw in body.companies:
        name = (raw or "").strip()
        if not name:
            continue
        if name.lower() in seen_lower:
            continue
        seen_lower.add(name.lower())
        companies.append(name[:50])
    if len(companies) < 2:
        from fastapi import HTTPException

        raise HTTPException(status_code=422, detail="Provide 2-4 distinct companies")
    companies = companies[:4]

    user_id = user.get("user_id")
    if user_id:
        ensure_user(user_id, user.get("email"))

    results = []
    for company in companies:
        q = f"{company} {body.query}".strip() if body.query.strip() else company
        try:
            evidence = await retrieve_evidence(q, k=body.k)
        except Exception as e:
            logger.warning(f"compare retrieval failed for {company}: {e}")
            evidence = []
        confidence = compute_confidence(evidence)
        try:
            impact = get_impact(company, depth=body.depth)
            suppliers = get_suppliers(company, depth=body.depth)
        except Exception:
            impact, suppliers = {}, {}
        top_down = sorted(impact.items(), key=lambda kv: kv[1].get("score", 0), reverse=True)[:3]
        top_up = sorted(suppliers.items(), key=lambda kv: kv[1].get("score", 0), reverse=True)[:3]
        summary = _summarize_evidence(evidence)
        results.append(
            {
                "company": company,
                "query_used": q,
                "evidence_count": len(evidence),
                "signal_strength": confidence.get("score", 0),
                "confidence": confidence,
                "evidence": [e.model_dump() for e in evidence],
                "summary": summary,
                "downstream_count": len(impact),
                "top_downstream": [{"company": k, "score": v.get("score", 0)} for k, v in top_down],
                "suppliers_count": len(suppliers),
                "top_suppliers": [{"company": k, "score": v.get("score", 0)} for k, v in top_up],
                "impact": {k: {"score": v.get("score", 0), "distance": v.get("distance", 1)} for k, v in list(impact.items())[:8]},
                "suppliers": {k: {"score": v.get("score", 0), "distance": v.get("distance", 1)} for k, v in list(suppliers.items())[:8]},
            }
        )

    # Overlap: downstream / upstream nodes shared by >=2 compared companies
    def _overlap(field: str) -> list[dict]:
        counts: dict[str, list[str]] = {}
        for r in results:
            for node in r.get(field, {}):
                counts.setdefault(node, []).append(r["company"])
        return [
            {"company": node, "shared_by": sorted(owners), "count": len(owners)}
            for node, owners in sorted(counts.items(), key=lambda kv: (-len(kv[1]), kv[0]))
            if len(owners) >= 2
        ][:8]

    title_sets: dict[str, set] = {}
    for r in results:
        title_sets[r["company"]] = {(e.get("title"), e.get("source")) for e in r["evidence"]}
    shared_evidence: list[dict] = []
    if len(results) >= 2:
        from itertools import combinations

        for a, b in combinations(results, 2):
            common = title_sets[a["company"]] & title_sets[b["company"]]
            for title, source in list(common)[:5]:
                shared_evidence.append({"title": title, "source": source, "shared_by": sorted([a["company"], b["company"]])})

    overlap = {
        "shared_downstream": _overlap("impact"),
        "shared_upstream": _overlap("suppliers"),
        "shared_evidence": shared_evidence[:8],
    }

    # LLM comparative verdict (same section schema as /generate for StrategicInsightReport)
    comparison_report = None
    status = "success"
    if not settings.gemini_api_key:
        status = "simulated"
        comparison_report = json.dumps(
            {
                "sections": [
                    {"id": "evidence", "title": "Comparison Evidence", "points": [f"{r['company']}: {r['evidence_count']} signals, strength {r['signal_strength']} ({r['confidence'].get('label', 'LOW')})" for r in results]},
                    {"id": "change", "title": "What Changed", "points": ["Gemini API key missing — showing retrieval snapshot only. Configure GEMINI_API_KEY for an LLM verdict."]},
                    {"id": "confidence", "title": "Confidence Meter", "value": "Low", "reason": "Simulation mode, no LLM synthesis."},
                    {"id": "ceo", "title": "CEO Summary", "text": " ".join(f"{r['company']} shows {r['evidence_count']} signals." for r in results)},
                ]
            }
        )
    else:
        try:
            lines = []
            for r in results:
                lines.append(
                    f"- {r['company']}: {r['evidence_count']} signals, strength {r['signal_strength']}, "
                    f"downstream {r['downstream_count']} (top: {', '.join(x['company'] for x in r['top_downstream']) or 'none'}), "
                    f"suppliers {r['suppliers_count']}, latest: {r['summary']['latest_title'] or 'none'}"
                )
            overlap_lines = []
            for o in overlap["shared_downstream"][:4]:
                overlap_lines.append(f"shared downstream {o['company']} via {', '.join(o['shared_by'])}")
            evidence_context = "\n".join(
                f"[{item.get('timestamp') or 'N/A'} | {item.get('source') or 'Unknown'}] {item.get('title') or 'Untitled'}\n"
                f"Snippet: {item.get('snippet') or ''}"
                for result in results for item in result["evidence"]
            )
            prompt = f"""You are SiliconPulse, a semiconductor strategy analyst.
{SYSTEM_INSTRUCTION_HIERARCHY}
Compare these companies head-to-head using the counts and graph relationships in the data below. Output only JSON matching the report schema, with unique section IDs and required evidence, confidence, and ceo sections. For each factual claim, cite source, timestamp, title and an exact verbatim span from retrieved evidence. Do not invent facts.
USER CONTEXT: {body.query or 'recent signals'}
{untrusted_block("COMPARISON_DATA", {"companies": companies, "per_company": lines, "graph_overlap": overlap_lines})}
{untrusted_block("RETRIEVED_EVIDENCE", evidence_context)}"""
            raw = await gemini_client.generate_content_with_fallback(prompt, response_schema=InsightReport)
            validated = validate_insight_report(raw)
            validated, omitted_claims = ground_insight_report(validated, evidence_context)
            if omitted_claims:
                logger.info("Omitted %s comparison claims without verified evidence spans", omitted_claims)
            comparison_report = validated.model_dump_json()
        except Exception as e:
            logger.warning(f"compare LLM failed: {e}")
            status = "fallback"
            comparison_report = json.dumps(
                {"sections": [{"id": "evidence", "title": "Comparison Evidence", "points": [f"{r['company']}: {r['evidence_count']} signals" for r in results]}, {"id": "confidence", "title": "Confidence Meter", "value": "Low", "reason": "LLM synthesis unavailable; counts are retrieval snapshots."}, {"id": "ceo", "title": "CEO Summary", "text": "LLM synthesis unavailable; table above reflects retrieval counts."}]}
            )

    return {
        "companies": results,
        "overlap": overlap,
        "comparison_report": comparison_report,
        "status": status,
        "model": settings.gemini_model,
        "queried_at": datetime.now().isoformat(),
        "extracted_entities": extract_companies(" ".join(companies)),
    }
