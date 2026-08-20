from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ..core.auth import get_current_user
from .store import get_edges, get_impact, get_nodes, get_suppliers

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
