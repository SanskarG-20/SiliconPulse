import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, Request

from ..company_dict import COMPANY_DICT
from ..core.auth import get_current_user
from ..core.limiter import limiter
from ..graph.store import get_impact, get_suppliers
from ..models import (
    EvidenceItem,
    GenerateRequest,
    GenerateResponse,
    QueryRequest,
    QueryResponse,
    RadarStatus,
)
from ..query_cache import query_cache
from ..services.embedding_service import embed_text
from ..services.gemini_client import gemini_client
from ..services.vector_store import is_available as vector_available
from ..services.vector_store import query_similar
from ..settings import settings
from ..supabase_client import ensure_user, insert_insight_record, insert_query_record
from ..utils import compute_confidence, extract_companies, safe_read_jsonl

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


@router.post("/query", response_model=QueryResponse)
@limiter.limit("30/minute")
async def process_query(request: Request, body: QueryRequest, user=Depends(get_current_user)):
    """
    Process a query and retrieve top-k evidence from the data stream.

    OPTIMIZED FOR SPEED:
    - Uses in-memory event cache (refreshes every 3s)
    - LRU query result cache (60s TTL)
    - Timing logs for performance monitoring
    - Limited snippet size (160 chars)
    """
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    user_id = user.get("user_id")
    user_email = user.get("email")

    try:
        cached_result = query_cache.get(body.query, body.k)
        if cached_result:
            if user_id:
                ensure_user(user_id, user_email)
                insert_query_record(
                    user_id=user_id,
                    query_text=body.query,
                    k=body.k,
                    evidence_count=len(cached_result.get("evidence", [])),
                    signal_strength=cached_result.get("signal_strength", 0),
                )
            logger.info(f"[{request_id}] Cache HIT - {body.query[:50]} - {(time.time() - start_time)*1000:.1f}ms")
            return QueryResponse(**cached_result)

        logger.info(f"[{request_id}] Query START - {body.query[:50]}")

        data_path = settings.resolved_data_path

        if not data_path.exists() and not vector_available():
            result = {
                "query": body.query,
                "evidence": [],
                "signal_strength": 0,
                "last_updated": datetime.now().isoformat()
            }
            if user_id:
                ensure_user(user_id, user_email)
                insert_query_record(
                    user_id=user_id,
                    query_text=body.query,
                    k=body.k,
                    evidence_count=0,
                    signal_strength=0,
                )
            query_cache.set(body.query, body.k, result)
            return QueryResponse(**result)

        matched_events = []
        db_search_successful = False

        # Attempt Database-level Hybrid Search (RRF)
        if vector_available():
            try:
                from ..services.vector_store import query_hybrid
                q_emb = await embed_text(body.query)
                if q_emb:
                    # Construct keyword text with aliases for full text search
                    raw_keywords = [kw.lower() for kw in body.query.split() if len(kw) > 2]
                    query_keywords = set(raw_keywords)
                    
                    for company, data in COMPANY_DICT.items():
                        aliases = [a.lower() for a in data.get("aliases", [])]
                        aliases.append(company.lower())
                        is_relevant = any(kw in aliases for kw in raw_keywords)
                        if is_relevant:
                            query_keywords.update(aliases)
                    
                    # Convert keywords to an OR query for websearch_to_tsquery
                    ts_query_parts = []
                    for kw in query_keywords:
                        if " " in kw:
                            ts_query_parts.append(f'"{kw}"')
                        else:
                            ts_query_parts.append(kw)
                    ts_query_text = " OR ".join(ts_query_parts) if ts_query_parts else body.query

                    # Execute DB search
                    db_hits = query_hybrid(ts_query_text, q_emb, k=body.k * 2)
                    
                    if db_hits is not None:
                        matched_events = db_hits
                        db_search_successful = True
                        logger.info(f"[{request_id}] Used DB Hybrid Search, found {len(db_hits)} hits.")
            except Exception as e:
                logger.warning(f"[{request_id}] DB Hybrid search failed, falling back to local: {e}")

        # Fallback to local file-based search
        if not db_search_successful:
            events = safe_read_jsonl(
                data_path,
                limit=settings.max_events_to_scan,
                freshness_hours=settings.freshness_hours
            )
            if not events:
                events = safe_read_jsonl(
                    data_path,
                    limit=settings.max_events_to_scan,
                    freshness_hours=None
                )
                if events:
                    logger.info(f"[{request_id}] No fresh events in {settings.freshness_hours}h window, fell back to stale ({len(events)} items)")

            vector_hits: dict[str, float] = {}
            if vector_available() and bool(events):
                try:
                    q_emb = await embed_text(body.query)
                    if q_emb:
                        similar = query_similar(q_emb, k=min(30, len(events) * 2))
                        for hit in similar:
                            t = hit.get("title", "")
                            if t:
                                vector_hits[t] = float(hit.get("similarity", 0.0))
                        logger.info(f"[{request_id}] Vector hits: {len(vector_hits)}")
                except Exception as ve:
                    logger.warning(f"[{request_id}] Vector search failed: {ve}")

            raw_keywords = [kw.lower() for kw in body.query.split() if len(kw) > 2]
            query_keywords = set(raw_keywords)
            for company, data in COMPANY_DICT.items():
                aliases = [a.lower() for a in data.get("aliases", [])]
                aliases.append(company.lower())
                is_relevant = False
                for kw in raw_keywords:
                    if kw in aliases:
                        is_relevant = True
                        break
                if is_relevant:
                    query_keywords.update(aliases)
            query_keywords = list(query_keywords)

            for event in events:
                title = event.get("title", "").lower()
                content = event.get("content", "").lower()
                company = event.get("company", "").lower() if event.get("company") else ""
                match_count = sum(1 for keyword in query_keywords if keyword in title or keyword in content or keyword in company)
                if match_count > 0:
                    matched_events.append(event)

            if vector_hits:
                seen_titles_kw = {e.get("title") for e in matched_events}
                for event in events:
                    t = event.get("title", "")
                    if t in vector_hits and t not in seen_titles_kw:
                        sim = vector_hits[t]
                        if sim >= 0.55:
                            matched_events.append(event)

            seen = set()
            unique_matched = []
            for event in matched_events:
                key = (event.get("title"), event.get("source"))
                if key not in seen:
                    seen.add(key)
                    unique_matched.append(event)
            matched_events = unique_matched

        evidence_list = []
        for event in matched_events:
            snippet = event.get("snippet", "")

            if not snippet or len(snippet) < 10:
                content = event.get("content", "")
                if content and len(content) > 20:
                    snippet = content[:200] + "..."
                else:
                    snippet = event.get("title", "")

            evidence_list.append(EvidenceItem(
                title=event.get("title", "Untitled"),
                snippet=snippet,
                source=event.get("source", "Unknown"),
                timestamp=event.get("timestamp", ""),
                url=event.get("url", ""),
                company=event.get("company"),
                event_type=event.get("event_type", "general")
            ))

        evidence_list.sort(key=lambda x: x.timestamp, reverse=True)
        evidence_list = evidence_list[:body.k]

        result = {
            "query": body.query,
            "evidence": evidence_list,
            "signal_strength": compute_confidence(evidence_list)["score"],
            "confidence": compute_confidence(evidence_list),
            "last_updated": datetime.now().isoformat(),
            "report": None,
            "llm_status": "pending",
            "stream_path_used": str(data_path)
        }

        query_cache.set(body.query, body.k, result)

        if user_id:
            ensure_user(user_id, user_email)
            insert_query_record(
                user_id=user_id,
                query_text=body.query,
                k=body.k,
                evidence_count=len(evidence_list),
                signal_strength=result["signal_strength"],
            )

        logger.info(f"[{request_id}] Query END - Found {len(evidence_list)} items - {(time.time() - start_time)*1000:.1f}ms")
        return QueryResponse(**result)

    except Exception as e:
        logger.error(f"Query Error: {e}")
        return QueryResponse(
            query=body.query,
            evidence=[],
            signal_strength=0,
            confidence=compute_confidence([]),
            last_updated=datetime.now().isoformat(),
            report=None,
            llm_status="failed"
        )


@router.get("/radar", response_model=list[RadarStatus])
async def get_radar():
    """Get radar status for all companies based on recent activity."""
    try:
        data_path = settings.resolved_data_path
        if not data_path.exists():
            return []

        events = safe_read_jsonl(
            data_path,
            limit=settings.max_events_to_scan,
            freshness_hours=settings.freshness_hours
        )
        if not events:
            events = safe_read_jsonl(
                data_path,
                limit=settings.max_events_to_scan,
                freshness_hours=None
            )

        company_counts = {}
        for event in events:
            company = event.get("company")
            if company:
                company_counts[company] = company_counts.get(company, 0) + 1

        radar_list = []
        for company, count in company_counts.items():
            if count >= 5:
                activity = "High"
            elif count >= 2:
                activity = "Moderate"
            else:
                activity = "Low"

            radar_list.append(RadarStatus(
                company=company,
                activity_level=activity,
                count=count
            ))

        radar_list.sort(key=lambda x: x.count, reverse=True)
        return radar_list[:15]

    except Exception as e:
        logger.error(f"Radar Error: {e}")
        return []


@router.post("/generate", response_model=GenerateResponse)
@limiter.limit("10/minute")
async def generate_insight(request: Request, body: GenerateRequest, user=Depends(get_current_user)):
    """Generate insight using Gemini based on query and context."""
    try:
        user_id = user.get("user_id")
        user_email = user.get("email")

        if not settings.gemini_api_key:
            fallback_text = "**Simulation Mode**\n\nGemini API Key is missing. Please configure `GEMINI_API_KEY` in `.env` for live AI insights.\n\nBased on the available signals, market activity appears elevated with significant movement in the semiconductor sector."
            if user_id:
                ensure_user(user_id, user_email)
                insert_insight_record(
                    user_id=user_id,
                    query_text=body.query,
                    insight=fallback_text,
                    model_name=settings.gemini_model,
                    status="simulated",
                )
            return GenerateResponse(insight=fallback_text)

        # Robust evidence counting: frontend builds "LIVE UPDATES CONTEXT:\n[ts | source] ..." so an empty context is "".
        # Counting "[20" is fragile (year-dependent); count evidence delimiters instead.
        stripped = body.context.strip() if body.context else ""
        if not stripped or stripped == "LIVE UPDATES CONTEXT:":
            evidence_count = 0
        else:
            # Each evidence block starts with "["; count them.
            evidence_count = stripped.count("[")
            # Fallback: if no "[" found but context is non-empty, treat as having evidence
            if evidence_count == 0 and len(stripped) > 20:
                evidence_count = 1
        logger.info(f"Generating insight for query: '{body.query}' | Evidence Count: {evidence_count} | Context Len: {len(body.context)}")

        if evidence_count == 0:
            logger.info("Zero evidence found. Generating structured fallback.")

            data_path = settings.resolved_data_path
            latest_events = safe_read_jsonl(data_path, limit=3)

            from ..company_dict import COMPANY_DICT
            suggestions = []
            query_upper = body.query.upper()

            matched_company = None
            for company, data in COMPANY_DICT.items():
                if query_upper in company.upper() or any(a.upper() in query_upper for a in data.get("aliases", [])):
                    matched_company = company
                    break

            if matched_company:
                suggestions = [f"Recent {matched_company} yield reports", f"{matched_company} supply chain updates", f"Competitor impact on {matched_company}"]
            else:
                suggestions = ["Top 3 high-impact events", "Semiconductor supply chain status", "AI infrastructure updates"]

            fallback_report = {
                "sections": [
                    {
                        "id": "evidence",
                        "title": "Insufficient Live Signals",
                        "points": [
                            f"No direct evidence found for '{body.query}' in the current data stream.",
                            "The system is actively monitoring global nodes for relevant signals."
                        ]
                    },
                    {
                        "id": "change",
                        "title": "Alternative Directives",
                        "points": suggestions
                    },
                    {
                        "id": "outlook",
                        "title": "Latest Global Signals",
                        "points": [f"[{e.get('source', 'Unknown')}] {e.get('title', 'Untitled')}" for e in latest_events] if latest_events else ["Monitoring for new signals..."]
                    },
                    {
                        "id": "confidence",
                        "title": "Confidence Meter",
                        "value": "Low",
                        "reason": "Zero matching evidence items found."
                    },
                    {
                        "id": "ceo",
                        "title": "System Status",
                        "text": "We are currently scanning for signals matching your query. In the meantime, consider the alternative directives or review the latest global feed above."
                    }
                ]
            }
            fallback_json = json.dumps(fallback_report)
            if user_id:
                ensure_user(user_id, user_email)
                insert_insight_record(
                    user_id=user_id,
                    query_text=body.query,
                    insight=fallback_json,
                    model_name=settings.gemini_model,
                    status="fallback",
                )
            return GenerateResponse(insight=fallback_json)

        # Graph RAG enrichment
        graph_parts = []
        try:
            companies_in_query = extract_companies(body.query)
            for comp in companies_in_query[:2]:
                impact = get_impact(comp, depth=2)
                suppliers = get_suppliers(comp, depth=2)
                if impact:
                    downstream = ", ".join([f"{k} (score {v['score']}, via {v['path'][0].relation})" for k, v in list(impact.items())[:4]])
                    graph_parts.append(f"DOWNSTREAM IMPACT of {comp}: {downstream}")
                if suppliers:
                    upstream = ", ".join([f"{k} (score {v['score']})" for k, v in list(suppliers.items())[:4]])
                    graph_parts.append(f"UPSTREAM SUPPLIERS of {comp}: {upstream}")
        except Exception as ge:
            logger.warning(f"Graph enrichment failed: {ge}")
        graph_context = "\n".join(graph_parts) if graph_parts else "No supply-chain graph data for query."

        from ..models import InsightReport
        
        prompt = f"""
        You are SiliconPulse, an advanced strategic intelligence engine.
        Generate a high-precision intelligence report based on the provided context.

        QUERY: {body.query}

        CONTEXT:
        {body.context}

        GRAPH CONTEXT (supply-chain relationships):
        {graph_context}

        INSTRUCTIONS:
        - Analyze the provided evidence carefully.
        - IMPORTANT: Even if there is only ONE evidence item, extract all possible facts and implications.
        - If evidence is low, focus on "What we know" vs "What we don't know".
        - Include uncertainties and monitoring suggestions in the "outlook" section.
        - Ensure the "confidence" section reflects the limited data (e.g., "Low" or "Medium").
        - For the "ceo" section, use the "text" field to provide a paragraph summary.
        - For other sections (like "evidence", "change", "impact", "competitors", "outlook"), provide a list of "points".
        """

        insight_text = await gemini_client.generate_content_with_fallback(prompt, response_schema=InsightReport)

        if user_id:
            ensure_user(user_id, user_email)
            insert_insight_record(
                user_id=user_id,
                query_text=body.query,
                insight=insight_text,
                model_name=settings.gemini_model,
                status="success",
            )

        return GenerateResponse(insight=insight_text)

    except Exception as e:
        logger.error(f"Gemini Generation Failed: {e}")
        failed_text = f"**Insight Generation Unavailable**\n\nWe encountered an issue connecting to the intelligence engine. However, the live data above remains accurate.\n\n*System Note: {str(e)}*"
        user_id = user.get("user_id")
        user_email = user.get("email")
        if user_id:
            ensure_user(user_id, user_email)
            insert_insight_record(
                user_id=user_id,
                query_text=body.query,
                insight=failed_text,
                model_name=settings.gemini_model,
                status="failed",
            )
        return GenerateResponse(insight=failed_text)
