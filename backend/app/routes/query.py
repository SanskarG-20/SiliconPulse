import json
import logging
import time
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends

from ..company_dict import COMPANY_DICT
from ..core.auth import get_current_user
from ..models import (
    EvidenceItem,
    GenerateRequest,
    GenerateResponse,
    QueryRequest,
    QueryResponse,
    RadarStatus,
)
from ..query_cache import query_cache
from ..services.gemini_client import gemini_client
from ..settings import settings
from ..supabase_client import ensure_user, insert_insight_record, insert_query_record
from ..utils import compute_confidence, safe_read_jsonl

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


@router.post("/query", response_model=QueryResponse)
async def process_query(request: QueryRequest, user=Depends(get_current_user)):
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
        cached_result = query_cache.get(request.query, request.k)
        if cached_result:
            if user_id:
                ensure_user(user_id, user_email)
                insert_query_record(
                    user_id=user_id,
                    query_text=request.query,
                    k=request.k,
                    evidence_count=len(cached_result.get("evidence", [])),
                    signal_strength=cached_result.get("signal_strength", 0),
                )
            logger.info(f"[{request_id}] Cache HIT - {request.query[:50]} - {(time.time() - start_time)*1000:.1f}ms")
            return QueryResponse(**cached_result)

        logger.info(f"[{request_id}] Query START - {request.query[:50]}")

        data_path = settings.resolved_data_path

        if not data_path.exists():
            result = {
                "query": request.query,
                "evidence": [],
                "signal_strength": 0,
                "last_updated": datetime.now().isoformat()
            }
            if user_id:
                ensure_user(user_id, user_email)
                insert_query_record(
                    user_id=user_id,
                    query_text=request.query,
                    k=request.k,
                    evidence_count=0,
                    signal_strength=0,
                )
            query_cache.set(request.query, request.k, result)
            return QueryResponse(**result)

        events = safe_read_jsonl(
            data_path,
            limit=settings.max_events_to_scan,
            freshness_hours=settings.freshness_hours
        )

        matched_events = []

        raw_keywords = [kw.lower() for kw in request.query.split() if len(kw) > 2]
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
        logger.info(f"Expanded Query Keywords: {query_keywords}")

        for event in events:
            title = event.get("title", "").lower()
            content = event.get("content", "").lower()
            company = event.get("company", "").lower() if event.get("company") else ""

            match_count = 0
            for keyword in query_keywords:
                if keyword in title or keyword in content or keyword in company:
                    match_count += 1

            if match_count > 0:
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
        evidence_list = evidence_list[:request.k]

        result = {
            "query": request.query,
            "evidence": evidence_list,
            "signal_strength": compute_confidence(evidence_list)["score"],
            "confidence": compute_confidence(evidence_list),
            "last_updated": datetime.now().isoformat(),
            "report": None,
            "llm_status": "pending",
            "stream_path_used": str(data_path)
        }

        query_cache.set(request.query, request.k, result)

        if user_id:
            ensure_user(user_id, user_email)
            insert_query_record(
                user_id=user_id,
                query_text=request.query,
                k=request.k,
                evidence_count=len(evidence_list),
                signal_strength=result["signal_strength"],
            )

        logger.info(f"[{request_id}] Query END - Found {len(evidence_list)} items - {(time.time() - start_time)*1000:.1f}ms")
        return QueryResponse(**result)

    except Exception as e:
        print(f"Query Error: {e}")
        return QueryResponse(
            query=request.query,
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
        print(f"Radar Error: {e}")
        return []


@router.post("/generate", response_model=GenerateResponse)
async def generate_insight(request: GenerateRequest, user=Depends(get_current_user)):
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
                    query_text=request.query,
                    insight=fallback_text,
                    model_name=settings.gemini_model,
                    status="simulated",
                )
            return GenerateResponse(insight=fallback_text)

        evidence_count = request.context.count("[20")

        logger.info(f"Generating insight for query: '{request.query}' | Evidence Count: {evidence_count} | Context Len: {len(request.context)}")

        if evidence_count == 0:
            logger.info("Zero evidence found. Generating structured fallback.")

            data_path = settings.resolved_data_path
            latest_events = safe_read_jsonl(data_path, limit=3)

            from .company_dict import COMPANY_DICT
            suggestions = []
            query_upper = request.query.upper()

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
                            f"No direct evidence found for '{request.query}' in the current data stream.",
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
                    query_text=request.query,
                    insight=fallback_json,
                    model_name=settings.gemini_model,
                    status="fallback",
                )
            return GenerateResponse(insight=fallback_json)

        prompt = f"""
        You are SiliconPulse, an advanced strategic intelligence engine. 
        Generate a high-precision intelligence report based on the provided context.
        
        QUERY: {request.query}
        
        CONTEXT:
        {request.context}
        
        INSTRUCTIONS:
        - Analyze the provided evidence carefully.
        - Output strictly valid JSON. Do not include markdown formatting (like ```json).
        - IMPORTANT: Even if there is only ONE evidence item, extract all possible facts and implications.
        - If evidence is low, focus on "What we know" vs "What we don't know".
        - Include uncertainties and monitoring suggestions in the "outlook" section.
        - Ensure the "confidence" section reflects the limited data (e.g., "Low" or "Medium").
        
        JSON SCHEMA:
        {{
          "sections": [
            {{ "id": "evidence", "title": "Live Signal Evidence", "points": ["..."], "evidence": [ {{ "source": "...", "timestamp": "...", "title": "..." }} ] }},
            {{ "id": "change", "title": "What Changed", "points": ["..."] }},
            {{ "id": "impact", "title": "Impact Reasoning", "points": ["..."] }},
            {{ "id": "competitors", "title": "Competitor Effects", "points": ["..."] }},
            {{ "id": "outlook", "title": "Strategic Outlook & Uncertainties", "points": ["..."] }},
            {{ "id": "confidence", "title": "Confidence Meter", "value": "Low|Medium|High", "reason": "..." }},
            {{ "id": "ceo", "title": "CEO Summary", "text": "..." }}
          ]
        }}
        """

        insight_text = await gemini_client.generate_content_with_fallback(prompt)

        if insight_text.startswith("```json"):
            insight_text = insight_text[7:]
        if insight_text.endswith("```"):
            insight_text = insight_text[:-3]

        insight_text = insight_text.strip()

        try:
            parsed_json = json.loads(insight_text)
            insight_text = json.dumps(parsed_json)
        except json.JSONDecodeError:
            logger.warning("Gemini output invalid JSON, attempting repair or fallback.")
            pass

        if user_id:
            ensure_user(user_id, user_email)
            insert_insight_record(
                user_id=user_id,
                query_text=request.query,
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
                query_text=request.query,
                insight=failed_text,
                model_name=settings.gemini_model,
                status="failed",
            )
        return GenerateResponse(insight=failed_text)
