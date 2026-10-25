"""Run a frozen report-trust benchmark against the local signal corpus.

The report metrics are deliberately deterministic heuristics, not a substitute
for human fact-checking: citation accuracy checks references resolve to retrieved
items, and hallucination rate checks claim-token support in those cited items.
"""
from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import logging
import re
import subprocess
from collections.abc import Iterable
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_GOLDEN = Path(__file__).with_name("golden_queries.json")
DEFAULT_CORPUS = ROOT / "backend" / "data" / "stream.jsonl"
DEFAULT_OUTPUT = Path(__file__).with_name("results") / "latest.json"
K = 5
_TOKEN_RE = re.compile(r"[a-z0-9]+", re.IGNORECASE)
_STOPWORDS = {
    "about", "after", "also", "among", "because", "been", "before", "being", "between",
    "could", "from", "have", "into", "more", "most", "other", "over", "said", "says",
    "some", "than", "that", "their", "there", "these", "they", "this", "through", "under",
    "were", "what", "when", "where", "which", "while", "with", "would", "will", "your",
}
logging.basicConfig(level=logging.WARNING)


def _tokens(value: str) -> set[str]:
    return {token.lower() for token in _TOKEN_RE.findall(value) if len(token) > 1 and token.lower() not in _STOPWORDS}


def _overlap_ratio(expected: str, observed: str) -> float:
    expected_tokens = _tokens(expected)
    if not expected_tokens:
        return 0.0
    return len(expected_tokens & _tokens(observed)) / len(expected_tokens)


def _domain(url: str | None) -> str:
    host = (urlparse(url or "").hostname or "").lower().rstrip(".")
    return host.removeprefix("www.")


def _evidence_text(item: dict) -> str:
    return " ".join(str(item.get(key) or "") for key in ("title", "snippet", "content", "company"))


def _claim_sentences(report: dict | None) -> Iterable[tuple[dict, str]]:
    for section in (report or {}).get("sections", []):
        if section.get("id") in {"evidence", "confidence"}:
            continue
        for point in section.get("points") or []:
            if str(point).strip():
                yield section, str(point).strip()
        text = str(section.get("text") or "")
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            if sentence.strip():
                yield section, sentence.strip()


def evaluate_case(case: dict, evidence: list[dict], report: dict | None, report_generation_attempted: bool = True) -> dict:
    """Compute query-level retrieval recall, citation resolution and support rates."""
    corpus_text = "\n".join(_evidence_text(item) for item in evidence)
    entities = case.get("expected_entities", [])
    domains = case.get("expected_source_domains", [])
    facts = case.get("key_facts", [])
    found_entities = sum(1 for expected in entities if _overlap_ratio(expected, corpus_text) >= 0.5)
    returned_domains = {_domain(item.get("url")) for item in evidence} - {""}
    found_domains = sum(1 for expected in domains if _domain("https://" + expected) in returned_domains)
    found_facts = sum(
        1 for fact in facts if any(_overlap_ratio(fact, _evidence_text(item)) >= 0.7 for item in evidence)
    )
    expected_total = len(entities) + len(domains) + len(facts)
    recall = (found_entities + found_domains + found_facts) / expected_total if expected_total else 1.0

    evidence_by_ref = {
        (str(item.get("source") or ""), str(item.get("timestamp") or ""), str(item.get("title") or "")): item
        for item in evidence
    }
    citations = []
    unsupported_claims = 0
    claims = list(_claim_sentences(report))
    for section, claim in claims:
        references = section.get("evidence") or []
        resolved = [
            evidence_by_ref.get((str(ref.get("source") or ""), str(ref.get("timestamp") or ""), str(ref.get("title") or "")))
            for ref in references
        ]
        resolved = [item for item in resolved if item is not None]
        citations.extend((ref, evidence_by_ref.get((str(ref.get("source") or ""), str(ref.get("timestamp") or ""), str(ref.get("title") or "")))) for ref in references)
        supported = False
        for item in resolved:
            cited_text = _evidence_text(item)
            claim_tokens = _tokens(claim)
            overlap = len(claim_tokens & _tokens(cited_text))
            if overlap >= 2 and overlap / max(1, len(claim_tokens)) >= 0.3:
                supported = True
                break
        if not supported:
            unsupported_claims += 1

    citation_accuracy = (
        sum(1 for _, item in citations if item is not None) / len(citations)
        if citations else (None if report is None else 0.0)
    )
    hallucination_rate = unsupported_claims / len(claims) if claims else (None if report is None else 0.0)
    return {
        "id": case.get("id"),
        "recall_at_k": recall,
        "entity_recall_at_k": found_entities / len(entities) if entities else 1.0,
        "source_domain_recall_at_k": found_domains / len(domains) if domains else 1.0,
        "key_fact_recall_at_k": found_facts / len(facts) if facts else 1.0,
        "citation_accuracy": citation_accuracy,
        "citation_count": len(citations),
        "report_claim_count": len(claims),
        "unsupported_claim_count": unsupported_claims,
        "hallucination_rate": hallucination_rate,
        "evidence_count": len(evidence),
        "generation_error": report is None and report_generation_attempted,
        "generation_not_run": not report_generation_attempted,
    }


def summarize(rows: list[dict]) -> dict:
    if not rows:
        return {"query_count": 0}
    keys = (
        "recall_at_k", "entity_recall_at_k", "source_domain_recall_at_k",
        "key_fact_recall_at_k", "citation_accuracy", "hallucination_rate",
    )
    return {
        "query_count": len(rows),
        **{
            key: round(sum(value for value in (row[key] for row in rows) if value is not None) / max(1, sum(row[key] is not None for row in rows)), 4)
            if any(row[key] is not None for row in rows) else None
            for key in keys
        },
        "citation_count": sum(row["citation_count"] for row in rows),
        "report_claim_count": sum(row["report_claim_count"] for row in rows),
        "unsupported_claim_count": sum(row["unsupported_claim_count"] for row in rows),
        "generation_error_count": sum(row["generation_error"] for row in rows),
        "generation_not_run_count": sum(row["generation_not_run"] for row in rows),
    }


def _read_events(path: Path) -> list[dict]:
    events = []
    with path.open(encoding="utf-8", errors="replace") as source:
        for line in source:
            try:
                item = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(item, dict):
                events.append(item)
    return events


def _load_golden(path: Path) -> list[dict]:
    cases = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(cases, list) or len(cases) != 50:
        raise ValueError("Golden set must contain exactly 50 cases")
    required = {"query", "expected_entities", "expected_source_domains", "key_facts"}
    if any(not isinstance(case, dict) or not required.issubset(case) for case in cases):
        raise ValueError("Every golden case must define query, expected_entities, expected_source_domains and key_facts")
    return cases


def _retrieve_all(cases: list[dict], corpus: list[dict], k: int) -> list[list[dict]]:
    """Exercise the HTTP retrieval route with its stores isolated to a frozen corpus."""
    from fastapi.testclient import TestClient
    from unittest.mock import patch

    from app.core.auth import get_current_user
    from app.core.limiter import limiter
    from app.main import app
    from app.query_cache import query_cache
    from app.utils import is_fresh

    def read_fixture(_path, limit=200, freshness_hours=None):
        selected = corpus[-max(limit, 1):]
        if freshness_hours is not None:
            selected = [item for item in selected if is_fresh(str(item.get("timestamp") or ""), freshness_hours)]
        return list(reversed(selected))

    previous_override = app.dependency_overrides.get(get_current_user)
    app.dependency_overrides[get_current_user] = lambda: {"user_id": None}
    limiter.enabled = False
    retrieved = []
    try:
        with patch("app.main.is_supabase_enabled", return_value=False), \
             patch("app.main.init_db"), \
             patch("app.routes.query.safe_read_jsonl", side_effect=read_fixture), \
             patch("app.routes.query.vector_available", return_value=False):
            with TestClient(app) as client:
                for case in cases:
                    query_cache.clear()
                    response = client.post("/api/query", json={"query": case["query"], "k": k})
                    response.raise_for_status()
                    retrieved.append(response.json().get("evidence", []))
    finally:
        if previous_override is None:
            app.dependency_overrides.pop(get_current_user, None)
        else:
            app.dependency_overrides[get_current_user] = previous_override
    return retrieved


def _context(evidence: list[dict]) -> str:
    lines = ["LIVE UPDATES CONTEXT:"]
    for item in evidence:
        lines.append(f"[{item.get('timestamp') or 'N/A'} | {item.get('source') or 'Unknown'}] {item.get('title') or 'Untitled'}")
        lines.append(f"Company: {item.get('company') or 'N/A'} | Event: {item.get('event_type') or 'General'}")
        lines.append(f"Snippet: {item.get('snippet') or ''}")
    return "\n".join(lines)


def _gemini_schema(value):
    """Strip the unsupported JSON Schema additionalProperties keyword recursively."""
    if isinstance(value, dict):
        return {key: _gemini_schema(item) for key, item in value.items() if key != "additionalProperties"}
    if isinstance(value, list):
        return [_gemini_schema(item) for item in value]
    return value


async def _generate_report(query: str, context: str) -> dict | None:
    from app.models import InsightReport
    from app.services.gemini_client import gemini_client
    from app.services.secure_prompt import SYSTEM_INSTRUCTION_HIERARCHY, untrusted_block, validate_insight_report

    if not gemini_client.available_models:
        return None
    schema = _gemini_schema(InsightReport.model_json_schema())
    prompt = f"""You are SiliconPulse, an evidence-based semiconductor and AI supply-chain analyst.
{SYSTEM_INSTRUCTION_HIERARCHY}
Analyze the query using only the supplied evidence. Return one JSON object matching this schema:
{schema}
The sections array must contain unique IDs and include evidence, confidence, and ceo sections.
For each factual section, include the exact source, timestamp, and title of evidence that supports it.
Query: {query}
{untrusted_block('RETRIEVED_EVIDENCE', context)}
"""
    try:
        # Call a single configured model per query; the application fallback loop
        # would multiply calls and violate common per-minute Gemini quotas.
        generate_once = gemini_client._generate_with_timeout.__wrapped__
        raw = await generate_once(
            gemini_client,
            gemini_client.available_models[0],
            prompt,
            response_schema=schema,
        )
        return validate_insight_report(raw).model_dump(mode="json")
    except Exception as exc:
        logging.getLogger(__name__).warning("Report generation/validation failed: %s: %s", type(exc).__name__, str(exc)[:160])
        return None


def run(
    golden_path: Path = DEFAULT_GOLDEN,
    corpus_path: Path = DEFAULT_CORPUS,
    output_path: Path = DEFAULT_OUTPUT,
    k: int = K,
    generation_interval_seconds: float = 13,
    generate_reports: bool = True,
) -> dict:
    cases = _load_golden(golden_path)
    corpus = _read_events(corpus_path)
    retrieved = _retrieve_all(cases, corpus, k)
    async def generate_all() -> list[dict | None]:
        reports = []
        for case, evidence in zip(cases, retrieved):
            if reports and generation_interval_seconds > 0:
                await asyncio.sleep(generation_interval_seconds)
            reports.append(await _generate_report(case["query"], _context(evidence)))
        return reports

    reports = asyncio.run(generate_all()) if generate_reports else [None] * len(cases)
    rows = []
    for case, evidence, report in zip(cases, retrieved, reports):
        rows.append(evaluate_case(case, evidence, report, report_generation_attempted=generate_reports))
    try:
        revision = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:
        revision = "unknown"
    output = {
        "run_at": datetime.now(timezone.utc).isoformat(),
        "revision": revision,
        "golden_set": str(golden_path.relative_to(ROOT)) if golden_path.is_relative_to(ROOT) else str(golden_path),
        "corpus": str(corpus_path.relative_to(ROOT)) if corpus_path.is_relative_to(ROOT) else str(corpus_path),
        "corpus_sha256": hashlib.sha256(corpus_path.read_bytes()).hexdigest(),
        "k": k,
        "generation_interval_seconds": generation_interval_seconds,
        "reports_generated": generate_reports,
        "report_generation_note": (
            None if generate_reports else "Skipped: Gemini free-tier quota was exhausted during the baseline attempt; report metrics are unavailable."
        ),
        "metric_definitions": {
            "recall_at_k": "Mean of expected-entity, expected-source-domain and key-fact recall in retrieved evidence.",
            "citation_accuracy": "Fraction of report evidence references that exactly resolve to a retrieved source/timestamp/title tuple.",
            "hallucination_rate": "Fraction of factual report claims with no cited retrieved item reaching 30% informative-token overlap (at least 2 tokens).",
        },
        "generation_mode": "Gemini JSON schema with unsupported additionalProperties fields removed; strict Pydantic validation applied locally",
        "metrics": summarize(rows),
        "cases": rows,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("-k", type=int, default=K)
    parser.add_argument("--generation-interval-seconds", type=float, default=13)
    parser.add_argument("--skip-generation", action="store_true", help="Evaluate retrieval only; report metrics are null without model reports")
    args = parser.parse_args()
    result = run(args.golden, args.corpus, args.output, args.k, args.generation_interval_seconds, not args.skip_generation)
    print(json.dumps(result["metrics"], indent=2))
    print(f"Detailed results: {args.output}")


if __name__ == "__main__":
    main()
