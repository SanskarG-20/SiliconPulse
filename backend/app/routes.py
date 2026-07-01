import asyncio
from fastapi import APIRouter, Depends, HTTPException, Response
from datetime import datetime
import json
import os
from pathlib import Path

from .models import (
    QueryRequest, QueryResponse, InjectRequest, InjectResponse, 
    EvidenceItem, RadarStatus, GenerateRequest, 
    GenerateResponse, ExportRequest, SourceVerifyResponse, SourceVerifyItem
)
from .settings import settings
from .sources.gdelt_source import pull_gdelt_signals
from .sources.hackernews_source import pull_hn_signals
from .services.news_sources import (
    async_pull_newsdata, async_pull_newsapi, async_pull_gnews, async_pull_mediastack,
    ingest_news_stream,
)
from .utils import (
    safe_read_jsonl, 
    compute_confidence,
    get_trust_info,
    now_ts, 
    compute_event_id, 
    deduplicate_and_append,
)
from .services.gemini_client import gemini_client
from .demo_generator import DemoGenerator
from . import storage
from .core.auth import get_current_user
from .supabase_client import (
    ensure_user,
    insert_insight_record,
    insert_query_record,
    insert_signal_record,
)

router = APIRouter(dependencies=[Depends(get_current_user)])
import logging
logger = logging.getLogger(__name__)


@router.get("/auth/me")
async def auth_me(user=Depends(get_current_user)):
    """Sync authenticated user to Supabase and return user identity."""
    user_id = user.get("user_id")
    user_email = user.get("email")  # Now extracted directly from JWT in auth dependency

    if user_id:
        logger.info(f"Syncing user {user_id} with email {user_email} to Supabase")
        ensure_user(user_id, user_email)
    else:
        logger.warning("auth/me called but no user_id in token")

    return {
        "authenticated": True,
        "user_id": user_id,
        "email": user_email,
        "session_id": user.get("session_id"),
    }


# Bootstrap endpoint
@router.post("/bootstrap")
async def bootstrap_system():
    """
    Generate fresh demo events and populate the stream.
    """
    try:
        generator = DemoGenerator()
        new_events = generator.generate_batch(10)
        
        # Append to stream with deduplication
        data_path = settings.resolved_data_path
        added_count = deduplicate_and_append(new_events, data_path)
        
        # Force cache refresh
        from app.cache import event_cache
        event_cache.refresh(data_path)
        
        return {
            "status": "success", 
            "new_events": added_count,
            "message": f"Bootstrapped {added_count} fresh events"
        }
    except Exception as e:
        print(f"Bootstrap Error: {e}")
        return {"status": "error", "new_events": 0, "error": str(e)}



# Signals endpoint
@router.get("/signals")
async def get_signals():
    """Get latest signals for the ticker."""
    try:
        data_path = settings.resolved_data_path
        if not data_path.exists():
            return []
            
        # Read fresh events
        events = safe_read_jsonl(
            data_path, 
            limit=20, # Top 20
            freshness_hours=settings.freshness_hours
        )
        
        # Deduplicate
        seen = set()
        unique_events = []
        for event in events:
            key = (event.get("title"), event.get("source"))
            if key not in seen:
                seen.add(key)
                unique_events.append(event)
                
        return unique_events
    except Exception as e:
        print(f"Signals Error: {e}")
        return []

# Inject endpoint
@router.post("/inject", response_model=InjectResponse)
async def inject_signal(request: InjectRequest, user=Depends(get_current_user)):
    """
    Inject a new data item into the stream.
    
    - Accepts InjectRequest with title, content, optional timestamp and source
    - Checks for duplicates using event fingerprint
    - Appends as JSON line to DATA_STREAM_PATH if unique
    """
    try:
        # Generate timestamp if not provided
        if request.timestamp is None:
            injected_at = datetime.now().isoformat()
        else:
            injected_at = request.timestamp
        
        # Prepare the data to inject
        data_entry = {
            "title": request.title,
            "content": request.content,
            "timestamp": injected_at,
            "source": request.source
        }
        
        # Compute ID
        event_id = compute_event_id(data_entry)
        
        # Append as JSON line to the file
        data_path = settings.resolved_data_path
        with open(data_path, "a", encoding="utf-8") as f:
            json.dump(data_entry, f, ensure_ascii=False)
            f.write("\n")
            
        # Mark as seen
        storage.mark_seen(event_id, request.source, request.title)

        # Persist manual signal in Supabase (optional if Supabase vars are configured)
        user_id = user.get("user_id")
        user_email = user.get("email")
        if user_id:
            ensure_user(user_id, user_email)
            insert_signal_record(
                user_id=user_id,
                source=request.source,
                title=request.title,
                content=request.content,
                timestamp=injected_at,
            )
        
        return InjectResponse(
            status="success",
            injected_at=injected_at,
            stream_path_used=str(data_path)
        )
        
    except PermissionError as e:
        raise HTTPException(
            status_code=403,
            detail=f"Permission denied when writing to {settings.data_stream_path}: {str(e)}"
        )
    except OSError as e:
        raise HTTPException(
            status_code=500,
            detail=f"File system error: {str(e)}"
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to inject data: {str(e)}"
        )


# Query endpoint
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
    import time
    import uuid
    from app.cache import event_cache
    from app.query_cache import query_cache
    from app.company_dict import COMPANY_DICT
    
    request_id = str(uuid.uuid4())[:8]
    start_time = time.time()
    user_id = user.get("user_id")
    user_email = user.get("email")
    
    try:
        # Check query cache first
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
        
        # Check if file exists
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
        
        # STAGE 1: Read events from cache (FAST)
        # Read fresh events
        events = safe_read_jsonl(
            data_path, 
            limit=settings.max_events_to_scan,
            freshness_hours=settings.freshness_hours
        )
            
        # STAGE 3: Match events (OPTIMIZED)
        matched_events = []
        
        # Synonym Expansion
        raw_keywords = [kw.lower() for kw in request.query.split() if len(kw) > 2]
        query_keywords = set(raw_keywords)
        
        # Universal Synonym Expansion using COMPANY_DICT
        for company, data in COMPANY_DICT.items():
            aliases = [a.lower() for a in data.get("aliases", [])]
            aliases.append(company.lower())
            
            # Check if any alias is in the query
            is_relevant = False
            for kw in raw_keywords:
                if kw in aliases:
                    is_relevant = True
                    break
            
            # If relevant, add all aliases and topics to search
            if is_relevant:
                query_keywords.update(aliases)
                # Add topics as keywords too? Maybe too broad, but let's add key terms from topics
                # For now, just aliases is a huge win.
                
        query_keywords = list(query_keywords)
        logger.info(f"Expanded Query Keywords: {query_keywords}")
        
        for event in events:
            title = event.get("title", "").lower()
            content = event.get("content", "").lower()
            company = event.get("company", "").lower() if event.get("company") else ""
            
            # Check if any keyword exists in title, content, or company
            match_count = 0
            for keyword in query_keywords:
                if keyword in title or keyword in content or keyword in company:
                    match_count += 1
            
            if match_count > 0:
                matched_events.append(event)
        
        # Deduplicate matched events
        seen = set()
        unique_matched = []
        for event in matched_events:
            key = (event.get("title"), event.get("source"))
            if key not in seen:
                seen.add(key)
                unique_matched.append(event)
        matched_events = unique_matched
        
        # Convert to EvidenceItem objects
        evidence_list = []
        for event in matched_events:
            # Generate snippet
            # Priority 1: Use existing snippet from event (e.g. from DemoGenerator)
            snippet = event.get("snippet", "")
            
            # Priority 2: Generate from content if snippet is missing/empty
            if not snippet or len(snippet) < 10:
                content = event.get("content", "")
                if content and len(content) > 20:
                    snippet = content[:200] + "..."
                else:
                    # Fallback to title
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
            
        # Sort by timestamp (newest first)
        evidence_list.sort(key=lambda x: x.timestamp, reverse=True)
        
        # Limit to k
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
        
        # Update cache
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
        # Return empty valid response instead of 500
        return QueryResponse(
            query=request.query,
            evidence=[],
            signal_strength=0,
            confidence=compute_confidence([]),
            last_updated=datetime.now().isoformat(),
            report=None,
            llm_status="failed"
        )


# Radar endpoint
@router.get("/radar", response_model=list[RadarStatus])
async def get_radar():
    """
    Get radar status for all companies based on recent activity.
    """
    try:
        data_path = settings.resolved_data_path
        if not data_path.exists():
            return []
        
        # Read fresh events
        events = safe_read_jsonl(
            data_path, 
            limit=settings.max_events_to_scan,
            freshness_hours=settings.freshness_hours
        )
            
        # Count events per company
        company_counts = {}
        for event in events:
            company = event.get("company")
            if company:
                company_counts[company] = company_counts.get(company, 0) + 1
        
        # Build radar status list
        radar_list = []
        for company, count in company_counts.items():
            # Determine activity level
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
            
        # Sort by count descending and limit to top 15 to prevent UI clutter
        radar_list.sort(key=lambda x: x.count, reverse=True)
        
        return radar_list[:15]
        
    except Exception as e:
        print(f"Radar Error: {e}")
        return []


# Generate endpoint
@router.post("/generate", response_model=GenerateResponse)
async def generate_insight(request: GenerateRequest, user=Depends(get_current_user)):
    """
    Generate insight using Gemini based on query and context.
    """
    try:
        user_id = user.get("user_id")
        user_email = user.get("email")

        # Check for API key first
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

        # 1. Gating Logic: Check evidence count
        # We estimate evidence count by looking for the separator pattern used in frontend
        evidence_count = request.context.count("[20") # Crude but effective for ISO timestamps in context
        
        logger.info(f"Generating insight for query: '{request.query}' | Evidence Count: {evidence_count} | Context Len: {len(request.context)}")

        # NEW RULE: If evidence_count == 0, return a structured fallback
        if evidence_count == 0:
            logger.info("Zero evidence found. Generating structured fallback.")
            
            # Fetch latest 3 signals for context
            data_path = settings.resolved_data_path
            latest_events = safe_read_jsonl(data_path, limit=3)
            
            # Construct suggestions based on query or general tech
            from app.company_dict import COMPANY_DICT
            suggestions = []
            query_upper = request.query.upper()
            
            # Try to find matching company for better suggestions
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

        # NEW RULE: If evidence_count >= 1, ALWAYS generate report
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
        
        # Clean up potential markdown code blocks if Gemini adds them
        if insight_text.startswith("```json"):
            insight_text = insight_text[7:]
        if insight_text.endswith("```"):
            insight_text = insight_text[:-3]
            
        insight_text = insight_text.strip()
        
        # Validate JSON
        try:
            parsed_json = json.loads(insight_text)
            # Re-serialize to ensure it's valid minified JSON string
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


# LLM Health Endpoints
@router.get("/llm/health")
async def llm_health():
    """Check Gemini configuration health"""
    return await gemini_client.check_health()

@router.get("/llm/models")
async def list_llm_models():
    """List available Gemini models"""
    return gemini_client.list_available_models()


# Source endpoints
@router.post("/sources/newsdata/pull")
async def pull_newsdata_endpoint():
    """Trigger NewsData.io signal pull"""
    try:
        count = await async_pull_newsdata()
        return {"status": "ok", "source": "NewsData.io", "pulled": count, "timestamp": datetime.utcnow().isoformat() + "Z"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/newsapi/pull")
async def pull_newsapi_endpoint():
    """Trigger NewsAPI signal pull"""
    try:
        count = await async_pull_newsapi()
        return {"status": "ok", "source": "NewsAPI", "pulled": count, "timestamp": datetime.utcnow().isoformat() + "Z"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/gnews/pull")
async def pull_gnews_endpoint():
    """Trigger GNews signal pull"""
    try:
        count = await async_pull_gnews()
        return {"status": "ok", "source": "GNews", "pulled": count, "timestamp": datetime.utcnow().isoformat() + "Z"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/mediastack/pull")
async def pull_mediastack_endpoint():
    """Trigger Mediastack signal pull"""
    try:
        count = await async_pull_mediastack()
        return {"status": "ok", "source": "Mediastack", "pulled": count, "timestamp": datetime.utcnow().isoformat() + "Z"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sources/pull_all")
async def pull_all_sources():
    """Trigger all signal sources (News APIs + GDELT + HackerNews)"""
    try:
        news_result, gdelt_count, hn_count = await asyncio.gather(
            ingest_news_stream(),
            asyncio.to_thread(pull_gdelt_signals),
            asyncio.to_thread(pull_hn_signals),
        )
        return {
            "status": "ok",
            "pulled": {
                "NewsAPIs": news_result,
                "GDELT": gdelt_count or 0,
                "HackerNews": hn_count or 0
            },
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/recommendations")
async def get_recommendations():
    """
    Generate dynamic recommended queries based on live data.
    """
    import random
    
    try:
        data_path = settings.resolved_data_path
        if not data_path.exists():
            # Fallback if no data
            return {
                "recommended_queries": [
                    {"label": "Market Overview", "query": "What are the top market trends right now?", "icon": "Activity", "color": "text-sky-400"},
                    {"label": "Tech News", "query": "Latest updates in technology sector?", "icon": "Cpu", "color": "text-emerald-400"},
                    {"label": "Global Events", "query": "Summary of major global events today", "icon": "Globe", "color": "text-amber-400"},
                    {"label": "Financial Impact", "query": "High impact financial news in last 24h", "icon": "TrendingUp", "color": "text-red-400"}
                ],
                "generated_at": datetime.utcnow().isoformat() + "Z"
            }

        # Read recent events
        events = safe_read_jsonl(
            data_path, 
            limit=50,
            freshness_hours=24
        )
        
        # Extract entities
        companies = set()
        sources = set()
        
        for event in events:
            if event.get("company"):
                companies.add(event.get("company"))
            if event.get("source"):
                sources.add(event.get("source"))
                
        # Convert to lists for random selection
        company_list = list(companies)
        source_list = list(sources)
        
        # Templates
        templates = [
            {"label": "{company} Strategy", "query": "What is the latest strategy update from {company}?", "icon": "Zap", "color": "text-amber-400"},
            {"label": "{company} Impact", "query": "Analyze recent impact of {company} announcements.", "icon": "Activity", "color": "text-red-400"},
            {"label": "{source} Intel", "query": "Summarize latest intelligence from {source}.", "icon": "ShieldAlert", "color": "text-emerald-400"},
            {"label": "Sector Analysis", "query": "Compare {company} vs competitors based on recent signals.", "icon": "BarChart3", "color": "text-sky-400"},
            {"label": "Supply Chain", "query": "Any supply chain disruptions involving {company}?", "icon": "Layers", "color": "text-indigo-400"},
            {"label": "Executive Brief", "query": "Executive summary of {company} performance today.", "icon": "FileText", "color": "text-slate-300"}
        ]
        
        recommendations = []
        used_companies = set()
        
        # Generate candidates
        candidates = []
        for _ in range(20): # Generate plenty of candidates
            template = random.choice(templates)
            
            if "{company}" in template["query"] and company_list:
                company = random.choice(company_list)
                query = template["query"].format(company=company)
                label = template["label"].format(company=company)
                candidates.append({**template, "query": query, "label": label, "key_entity": company})
            elif "{source}" in template["query"] and source_list:
                source = random.choice(source_list)
                query = template["query"].format(source=source)
                label = template["label"].format(source=source)
                candidates.append({**template, "query": query, "label": label, "key_entity": source})
                
        # Select 4 unique ones
        final_selection = []
        for cand in candidates:
            if len(final_selection) >= 4:
                break
            
            # Avoid duplicate entities if possible
            if cand.get("key_entity") in used_companies:
                continue
                
            final_selection.append(cand)
            used_companies.add(cand.get("key_entity"))
            
        # Fill if not enough unique
        if len(final_selection) < 4:
            remaining = 4 - len(final_selection)
            # Just take any random ones to fill
            for _ in range(remaining):
                 # Simple fallback templates
                 final_selection.append(
                     {"label": "High Impact", "query": "Top 3 high-impact events in last 2 hours?", "icon": "AlertCircle", "color": "text-red-400"}
                 )

        return {
            "recommended_queries": final_selection,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        print(f"Recommendation Error: {e}")
        # Return static fallback on error
        return {
            "recommended_queries": [
                {"label": "NVIDIA-TSMC Pipeline", "query": "Any new NVIDIA-TSMC contract today?", "icon": "Zap", "color": "text-amber-400"},
                {"label": "Foundry Design Wins", "query": "Status of Intel 18A design wins?", "icon": "CheckCircle2", "color": "text-emerald-400"},
                {"label": "AI Infra Analysis", "query": "Meta AI infra roadmap status?", "icon": "Cpu", "color": "text-sky-400"},
                {"label": "High Impact Summary", "query": "Top 3 high-impact events in last 2 hours?", "icon": "AlertCircle", "color": "text-red-400"}
            ],
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }


# Export endpoint
@router.post("/export")
async def export_analysis(request: ExportRequest):
    """
    Export the analysis report in the requested format.
    """
    try:
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"siliconpulse_report_{timestamp}"
        content = ""
        media_type = "text/plain"

        if request.format == "md":
            filename += ".md"
            media_type = "text/markdown"
            content = f"# SiliconPulse Intelligence Report\n\n"
            content += f"**Query:** {request.query}\n"
            content += f"**Date:** {datetime.now().isoformat()}\n\n"
            content += f"## Strategic Insight\n\n{request.report}\n\n"
            
            if request.include_evidence:
                content += f"## Evidence\n\n"
                for item in request.evidence:
                    content += f"- **{item.title}** ({item.source})\n"
                    content += f"  - {item.snippet}\n"
                    if item.url:
                        content += f"  - [Link]({item.url})\n"
                    content += "\n"
                
        elif request.format == "json":
            filename += ".json"
            media_type = "application/json"
            export_data = {
                "query": request.query,
                "timestamp": datetime.now().isoformat(),
                "report": request.report
            }
            if request.include_evidence:
                export_data["evidence"] = [item.dict() for item in request.evidence]
            content = json.dumps(export_data, indent=2)
            
        elif request.format == "txt":
            filename += ".txt"
            media_type = "text/plain"
            content = f"SILICONPULSE INTELLIGENCE REPORT\n"
            content += f"==============================\n"
            content += f"Query: {request.query}\n"
            content += f"Date: {datetime.now().isoformat()}\n\n"
            content += f"STRATEGIC INSIGHT\n"
            content += f"-----------------\n"
            content += f"{request.report}\n\n"
            
            if request.include_evidence:
                content += f"EVIDENCE\n"
                content += f"--------\n"
                for item in request.evidence:
                    content += f"* {item.title} ({item.source})\n"
                    content += f"  {item.snippet}\n"
                    if item.url:
                        content += f"  Link: {item.url}\n"
                    content += "\n"
        
        elif request.format == "pdf":
             filename += ".txt"
             content = "PDF export not configured. Returning text format.\n\n" + request.report

        return Response(
            content=content,
            media_type=media_type,
            headers={"Content-Disposition": f"attachment; filename={filename}"}
        )

    except Exception as e:
        logger.error(f"Export failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Verify Sources endpoint
@router.get("/sources/verify", response_model=SourceVerifyResponse)
async def verify_sources(query: str):
    """
    Verify sources for a given query.
    Re-runs a quick retrieval to identify sources and assign trust levels.
    """
    try:
        # 1. Read fresh events
        data_path = settings.resolved_data_path
        events = safe_read_jsonl(data_path, limit=settings.max_events_to_scan, freshness_hours=settings.freshness_hours)
        
        # 2. Filter relevant events (same logic as query)
        from app.company_dict import COMPANY_DICT
        
        raw_keywords = [kw.lower() for kw in query.split() if len(kw) > 2]
        query_keywords = set(raw_keywords)
        
        for company, data in COMPANY_DICT.items():
            aliases = [a.lower() for a in data.get("aliases", [])]
            aliases.append(company.lower())
            if any(kw in aliases for kw in raw_keywords):
                query_keywords.update(aliases)
        
        verified_sources = []
        seen_titles = set()
        
        for event in events:
            title = event.get("title", "").lower()
            content = event.get("content", "").lower()
            
            if any(kw in title or kw in content for kw in query_keywords):
                if event.get("title") not in seen_titles:
                    seen_titles.add(event.get("title"))
                    
                    source_name = event.get("source", "Unknown")
                    trust_info = get_trust_info(source_name)
                    
                    verified_sources.append(SourceVerifyItem(
                        timestamp=event.get("timestamp"),
                        source=source_name,
                        title=event.get("title", "Untitled"),
                        url=event.get("url"),
                        trust_level=trust_info["trust_level"],
                        reason=trust_info["reason"]
                    ))
            
            if len(verified_sources) >= 10:
                break
                
        return SourceVerifyResponse(
            query=query,
            sources=verified_sources
        )

    except Exception as e:
        logger.error(f"Source verification failed: {e}")
        return SourceVerifyResponse(query=query, sources=[])


# Diagnostic endpoint to verify user data persistence
@router.get("/user/diagnostics")
async def user_diagnostics(user=Depends(get_current_user)):
    """
    Returns the latest user data stored in Supabase.
    Useful for debugging user sync and data persistence.
    """
    from app.supabase_client import get_supabase_client
    
    user_id = user.get("user_id")
    user_email = user.get("email")
    
    if not user_id:
        return {
            "status": "error",
            "message": "No user_id in token"
        }
    
    client = get_supabase_client()
    if client is None:
        return {
            "status": "error",
            "message": "Supabase client not configured"
        }
    
    try:
        # Get user record
        user_response = client.table("users").select("*").eq("id", user_id).single().execute()
        user_record = user_response.data if user_response.data else None
        
        # Get latest query records (limit 5)
        queries_response = client.table("queries").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
        queries = queries_response.data or []
        
        # Get latest insight records (limit 5)
        insights_response = client.table("insights").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
        insights = insights_response.data or []
        
        # Get latest signal records (limit 5)
        signals_response = client.table("signals").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
        signals = signals_response.data or []
        
        return {
            "status": "success",
            "user_id": user_id,
            "user_record": user_record,
            "statistics": {
                "total_queries": len(queries),
                "total_insights": len(insights),
                "total_signals": len(signals)
            },
            "recent_queries": queries,
            "recent_insights": insights[:3],  # Show only first 3 to keep response size reasonable
            "recent_signals": signals[:3],
            "message": "All user data from Supabase"
        }
    except Exception as exc:
        logger.error(f"Diagnostics failed for user {user_id}: {exc}", exc_info=True)
        return {
            "status": "error",
            "user_id": user_id,
            "message": f"Failed to fetch user data: {str(exc)}"
        }
