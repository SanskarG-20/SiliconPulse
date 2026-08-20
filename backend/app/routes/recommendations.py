import logging
import random
from datetime import datetime

from fastapi import APIRouter, Depends

from ..core.auth import get_current_user
from ..settings import settings
from ..utils import safe_read_jsonl

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/recommendations")
async def get_recommendations():
    """Generate dynamic recommended queries based on live data."""
    try:
        data_path = settings.resolved_data_path
        if not data_path.exists():
            return {
                "recommended_queries": [
                    {"label": "Market Overview", "query": "What are the top market trends right now?", "icon": "Activity", "color": "text-sky-400"},
                    {"label": "Tech News", "query": "Latest updates in technology sector?", "icon": "Cpu", "color": "text-emerald-400"},
                    {"label": "Global Events", "query": "Summary of major global events today", "icon": "Globe", "color": "text-amber-400"},
                    {"label": "Financial Impact", "query": "High impact financial news in last 24h", "icon": "TrendingUp", "color": "text-red-400"}
                ],
                "generated_at": datetime.utcnow().isoformat() + "Z"
            }

        events = safe_read_jsonl(
            data_path,
            limit=50,
            freshness_hours=24
        )

        companies = set()
        sources = set()

        for event in events:
            if event.get("company"):
                companies.add(event.get("company"))
            if event.get("source"):
                sources.add(event.get("source"))

        company_list = list(companies)
        source_list = list(sources)

        templates = [
            {"label": "{company} Strategy", "query": "What is the latest strategy update from {company}?", "icon": "Zap", "color": "text-amber-400"},
            {"label": "{company} Impact", "query": "Analyze recent impact of {company} announcements.", "icon": "Activity", "color": "text-red-400"},
            {"label": "{source} Intel", "query": "Summarize latest intelligence from {source}.", "icon": "ShieldAlert", "color": "text-emerald-400"},
            {"label": "Sector Analysis", "query": "Compare {company} vs competitors based on recent signals.", "icon": "BarChart3", "color": "text-sky-400"},
            {"label": "Supply Chain", "query": "Any supply chain disruptions involving {company}?", "icon": "Layers", "color": "text-indigo-400"},
            {"label": "Executive Brief", "query": "Executive summary of {company} performance today.", "icon": "FileText", "color": "text-slate-300"}
        ]

        candidates = []
        for _ in range(20):
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

        final_selection = []
        used_companies = set()

        for cand in candidates:
            if len(final_selection) >= 4:
                break

            if cand.get("key_entity") in used_companies:
                continue

            final_selection.append(cand)
            used_companies.add(cand.get("key_entity"))

        if len(final_selection) < 4:
            remaining = 4 - len(final_selection)
            for _ in range(remaining):
                final_selection.append(
                    {"label": "High Impact", "query": "Top 3 high-impact events in last 2 hours?", "icon": "AlertCircle", "color": "text-red-400"}
                )

        return {
            "recommended_queries": final_selection,
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }

    except Exception as e:
        logger.error(f"Recommendation Error: {e}")
        return {
            "recommended_queries": [
                {"label": "NVIDIA-TSMC Pipeline", "query": "Any new NVIDIA-TSMC contract today?", "icon": "Zap", "color": "text-amber-400"},
                {"label": "Foundry Design Wins", "query": "Status of Intel 18A design wins?", "icon": "CheckCircle2", "color": "text-emerald-400"},
                {"label": "AI Infra Analysis", "query": "Meta AI infra roadmap status?", "icon": "Cpu", "color": "text-sky-400"},
                {"label": "High Impact Summary", "query": "Top 3 high-impact events in last 2 hours?", "icon": "AlertCircle", "color": "text-red-400"}
            ],
            "generated_at": datetime.utcnow().isoformat() + "Z"
        }
