from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, Field

from ..core.auth import get_current_user
from ..core.limiter import limiter
from ..settings import settings
from .store import get_edges, get_impact, get_nodes, get_suppliers, simulate_scenario

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/nodes")
async def graph_nodes():
    return {"nodes": get_nodes()}


@router.get("/edges")
async def graph_edges():
    return {"edges": [e.__dict__ for e in get_edges()]}


@router.get("/impact/{company}")
async def graph_impact(company: str, depth: int = Query(default=2, ge=1, le=3)):
    data = get_impact(company, depth=depth)
    if not data:
        # check if company exists at all
        if company.lower() not in [n.lower() for n in get_nodes()]:
            raise HTTPException(status_code=404, detail=f"Company '{company}' not in graph")
    # serialize
    out = {}
    for k, v in data.items():
        out[k] = {
            "distance": v["distance"],
            "score": v["score"],
            "path": [e.__dict__ for e in v["path"]],
        }
    return {"company": company, "depth": depth, "impact": out}


@router.get("/suppliers/{company}")
async def graph_suppliers(company: str, depth: int = Query(default=2, ge=1, le=3)):
    data = get_suppliers(company, depth=depth)
    if not data:
        if company.lower() not in [n.lower() for n in get_nodes()]:
            raise HTTPException(status_code=404, detail=f"Company '{company}' not in graph")
    out = {}
    for k, v in data.items():
        out[k] = {
            "distance": v["distance"],
            "score": v["score"],
            "path": [e.__dict__ for e in v["path"]],
        }
    return {"company": company, "depth": depth, "suppliers": out}


@router.get("/explain/{company}")
async def graph_explain(company: str, depth: int = Query(default=2, ge=1, le=3)):
    """LLM-ready explanation of supply-chain context for a company."""
    if company.lower() not in [n.lower() for n in get_nodes()]:
        raise HTTPException(status_code=404, detail=f"Company '{company}' not in graph")
    impact = get_impact(company, depth=depth)
    suppliers = get_suppliers(company, depth=depth)
    lines = [f"Supply-chain context for {company} (depth {depth}):"]
    if suppliers:
        lines.append("Upstream suppliers:")
        for k, v in list(suppliers.items())[:5]:
            path_str = " -> ".join([f"{e.source} -[{e.relation}]-> {e.target}" for e in v["path"]])
            lines.append(f"  - {k} (score {v['score']}): {path_str}")
    else:
        lines.append("Upstream suppliers: none")
    if impact:
        lines.append("Downstream impact:")
        for k, v in list(impact.items())[:5]:
            path_str = " -> ".join([f"{e.source} -[{e.relation}]-> {e.target}" for e in v["path"]])
            lines.append(f"  - {k} (score {v['score']}): {path_str}")
    else:
        lines.append("Downstream impact: none")
    return {"company": company, "depth": depth, "context": "\n".join(lines), "impact": impact, "suppliers": suppliers}


class SimulateRequest(BaseModel):
    company: str = Field(..., min_length=1, max_length=50, description="Company to shock")
    shock: float = Field(..., ge=-0.9, le=0.9, description="Shock factor: -0.1 = -10% yield/capacity")
    depth: int = Field(default=2, ge=1, le=3, description="BFS depth")
    metric: str = Field(default="yield", description="Metric shocked (yield, capacity, supply)")


@router.post("/simulate")
@limiter.limit("15/minute")
async def graph_simulate(request: Request, body: SimulateRequest, user=Depends(get_current_user)):
    """
    Simulate a supply-chain shock and generate an LLM scenario report.
    Shock -0.1 = TSMC N2 yield -10% → downstream NVIDIA, Microsoft etc. are scored as shocked_score = original * (1+shock).
    """

    # Validate company exists
    if body.company.lower() not in [n.lower() for n in get_nodes()]:
        raise HTTPException(status_code=404, detail=f"Company '{body.company}' not in graph")

    # Get shocked impact
    shocked = simulate_scenario(body.company, body.shock, depth=body.depth)
    # Build human-readable impact lines
    impact_lines = []
    for target, info in list(shocked.items())[:6]:
        impact_lines.append(
            f"{target}: {info['original_score']} → {info['shocked_score']} (Δ {info['delta']}, {info['severity']}, est ${info['est_impact_usd_m']}M)"
        )
    impact_text = "\n".join(impact_lines) if impact_lines else "No downstream impact"

    # Try to generate LLM scenario report (graceful fallback if no key)
    scenario_report = None
    if settings.gemini_api_key:
        try:
            from ..services.gemini_client import gemini_client

            shock_pct = int(body.shock * 100)
            prompt = f"""
You are SiliconPulse Scenario Engine. Simulate a supply-chain shock.

COMPANY: {body.company}
SHOCK: {shock_pct}% change in {body.metric} (factor {1+body.shock:.2f})
DEPTH: {body.depth}

GRAPH IMPACT (shocked):
{impact_text}

INSTRUCTIONS:
- Output valid JSON with sections: evidence, change, impact, competitors, outlook, confidence, ceo
- Quantify downstream $M impact using est_impact_usd_m
- Suggest mitigations (dual-source, inventory, alternative fab)
- Keep confidence Medium/Low due to simulation uncertainty
JSON SCHEMA: {{"sections": [{{"id":"evidence","title":"Shock Evidence","points":[...]}}]}}
"""
            scenario_report = await gemini_client.generate_content_with_fallback(prompt)
            # Ensure valid JSON string
            import json

            try:
                json.loads(scenario_report)
            except Exception:
                pass
        except Exception as e:
            import logging

            logging.getLogger(__name__).warning(f"Scenario LLM failed: {e}")

    # Serialize shocked (Edge objects)
    serial_shocked = {}
    for k, v in shocked.items():
        serial_shocked[k] = {
            "distance": v["distance"],
            "original_score": v["original_score"],
            "shocked_score": v["shocked_score"],
            "delta": v["delta"],
            "est_impact_usd_m": v["est_impact_usd_m"],
            "severity": v["severity"],
            "path": [e.__dict__ for e in v["path"]],
        }

    return {
        "company": body.company,
        "shock": body.shock,
        "metric": body.metric,
        "depth": body.depth,
        "factor": round(1 + body.shock, 3),
        "impact": serial_shocked,
        "impact_text": impact_text,
        "scenario_report": scenario_report,
    }
