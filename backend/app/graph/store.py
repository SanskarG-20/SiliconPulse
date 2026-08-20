from __future__ import annotations

"""
Simple in-memory supply-chain graph for Graph RAG POC.
Nodes = companies, Edges = dependency with type and weight.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class Edge:
    source: str
    target: str
    relation: str  # e.g. "supplies", "manufactures", "equips"
    weight: float = 1.0  # impact weight 0-1
    details: str = ""


# Static knowledge base - can be expanded or loaded from DB
EDGES: list[Edge] = [
    Edge("ASML", "TSMC", "supplies", 0.95, "EUV lithography"),
    Edge("ASML", "Samsung", "supplies", 0.9, "EUV lithography"),
    Edge("Applied Materials", "TSMC", "equips", 0.7, "deposition/etch"),
    Edge("Lam Research", "TSMC", "equips", 0.7, "etch"),
    Edge("TSMC", "NVIDIA", "manufactures", 0.95, "CoWoS, N3/N2"),
    Edge("TSMC", "Apple", "manufactures", 0.9, "N3/N2"),
    Edge("TSMC", "AMD", "manufactures", 0.85, "N3/N5"),
    Edge("TSMC", "Google", "manufactures", 0.6, "TPU"),
    Edge("Samsung", "NVIDIA", "supplies", 0.6, "HBM3e"),
    Edge("Micron", "NVIDIA", "supplies", 0.6, "HBM3e"),
    Edge("Samsung", "Apple", "supplies", 0.5, "memory"),
    Edge("NVIDIA", "Microsoft", "supplies", 0.8, "DGX/H100 for Azure"),
    Edge("NVIDIA", "Meta", "supplies", 0.8, "DGX/H100"),
    Edge("NVIDIA", "Amazon", "supplies", 0.7, "GPU for AWS"),
    Edge("AMD", "Microsoft", "supplies", 0.5, "MI300 for Azure"),
    Edge("Intel", "Microsoft", "supplies", 0.4, "18A foundry attempt"),
    Edge("Google", "Anthropic", "supplies", 0.5, "TPU/GCP"),
    Edge("Microsoft", "OpenAI", "invests", 0.9, "Azure + OpenAI"),
    Edge("Amazon", "Anthropic", "invests", 0.85, "Bedrock + Claude"),
]

# Build adjacency for fast lookup
_ADJ = {}
for e in EDGES:
    _ADJ.setdefault(e.source, []).append(e)
    _ADJ.setdefault(e.target, [])  # ensure node exists


def get_nodes() -> list[str]:
    return sorted(_ADJ.keys())


def get_edges() -> list[Edge]:
    return list(EDGES)


def get_impact(company: str, depth: int = 2) -> dict:
    """
    BFS from company to find downstream impact up to depth.
    Returns {node: {"distance": int, "path": [Edge, ...], "score": float}}
    Score = product of weights along path.
    """
    company = company.strip()
    # case-insensitive match
    canonical = next((n for n in _ADJ if n.lower() == company.lower()), None)
    if not canonical:
        return {}

    result: dict[str, dict] = {}
    queue: list[tuple[str, list[Edge], float, int]] = [(canonical, [], 1.0, 0)]
    visited = {canonical}

    while queue:
        cur, path, score, d = queue.pop(0)
        if d >= depth:
            continue
        for edge in _ADJ.get(cur, []):
            nxt = edge.target
            new_score = score * edge.weight
            new_path = path + [edge]
            if nxt not in result or new_score > result[nxt]["score"]:
                result[nxt] = {"distance": d + 1, "path": new_path, "score": round(new_score, 3)}
            if nxt not in visited:
                visited.add(nxt)
                queue.append((nxt, new_path, new_score, d + 1))
    # remove self if present
    result.pop(canonical, None)
    return result


def get_suppliers(company: str, depth: int = 2) -> dict:
    """Reverse BFS to find upstream suppliers."""
    company = company.strip()
    canonical = next((n for n in _ADJ if n.lower() == company.lower()), None)
    if not canonical:
        return {}
    # Build reverse adjacency
    rev: dict[str, list[Edge]] = {}
    for e in EDGES:
        rev.setdefault(e.target, []).append(e)
    result: dict[str, dict] = {}
    queue: list[tuple[str, list[Edge], float, int]] = [(canonical, [], 1.0, 0)]
    visited = {canonical}
    while queue:
        cur, path, score, d = queue.pop(0)
        if d >= depth:
            continue
        for edge in rev.get(cur, []):
            src = edge.source
            new_score = score * edge.weight
            new_path = [edge] + path
            if src not in result or new_score > result[src]["score"]:
                result[src] = {"distance": d + 1, "path": new_path, "score": round(new_score, 3)}
            if src not in visited:
                visited.add(src)
                queue.append((src, new_path, new_score, d + 1))
    result.pop(canonical, None)
    return result


def simulate_scenario(company: str, shock: float, depth: int = 2) -> dict:
    """
    Simulate a shock at `company` (e.g. yield -0.1 = -10%).
    `shock` in (-0.9, 0.9): -0.1 = -10% capacity/yield.
    Returns downstream impact with original vs shocked scores and delta.
    Shocked score = original_score * (1 + shock)  (linear propagation).
    """
    base = get_impact(company, depth=depth)
    if not base:
        return {}
    factor = 1.0 + shock
    # Clamp factor to avoid negative
    factor = max(0.05, factor)
    result: dict[str, dict] = {}
    for node, info in base.items():
        orig = info["score"]
        shocked = round(orig * factor, 3)
        delta = round(shocked - orig, 3)
        # Simple USD estimate: assume $1B baseline per 0.1 score (illustrative)
        est_usd_m = int(abs(delta) * 10000)  # e.g. delta -0.095 -> 950M
        result[node] = {
            "distance": info["distance"],
            "path": info["path"],
            "original_score": orig,
            "shocked_score": shocked,
            "delta": delta,
            "est_impact_usd_m": est_usd_m,
            "severity": "High" if abs(delta) > 0.15 else "Medium" if abs(delta) > 0.07 else "Low",
        }
    return result
