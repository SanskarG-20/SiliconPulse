"""Shared evidence retrieval used by /query and /compare.

Mirrors the retrieval stages in routes/query.py (DB hybrid -> local
keyword + vector fallback) so comparison results stay consistent with
single-query results. query.py itself is intentionally untouched.
"""
import logging

from .company_dict import COMPANY_DICT
from .models import EvidenceItem
from .services.embedding_service import embed_text
from .services.freshness_policy import filter_by_freshness
from .services.indexed_retrieval import reciprocal_rank_fusion, rerank_results, search_local_signals
from .services.vector_store import is_available as vector_available
from .services.vector_store import query_similar
from .settings import settings
from .utils import safe_read_jsonl

logger = logging.getLogger(__name__)


def _expand_keywords(query_text: str) -> list[str]:
    raw_keywords = [kw.lower() for kw in query_text.split() if len(kw) > 2]
    query_keywords = set(raw_keywords)
    for company, data in COMPANY_DICT.items():
        aliases = [a.lower() for a in data.get("aliases", [])]
        aliases.append(company.lower())
        if any(kw in aliases for kw in raw_keywords):
            query_keywords.update(aliases)
    return list(query_keywords)


def _to_evidence(matched_events: list[dict]) -> list[EvidenceItem]:
    evidence_list = []
    for event in matched_events:
        snippet = event.get("snippet", "")
        if not snippet or len(snippet) < 10:
            content = event.get("content", "")
            snippet = (content[:200] + "...") if content and len(content) > 20 else event.get("title", "")
        evidence_list.append(
            EvidenceItem(
                title=event.get("title", "Untitled"),
                snippet=snippet,
                source=event.get("source", "Unknown"),
                timestamp=event.get("timestamp", ""),
                url=event.get("url", ""),
                company=event.get("company"),
                event_type=event.get("event_type", "general"),
                freshness_status=event.get("freshness_status"),
                freshness_window_hours=event.get("freshness_window_hours"),
            )
        )
    evidence_list.sort(key=lambda x: x.timestamp, reverse=True)
    return evidence_list


async def retrieve_evidence(query_text: str, k: int = 5) -> list[EvidenceItem]:
    """Retrieve top-k evidence for a query string (DB hybrid, else local fallback)."""
    k = max(1, min(k, 20))
    matched_events: list[dict] = []
    db_search_successful = False

    if vector_available():
        try:
            from .services.vector_store import query_hybrid

            q_emb = await embed_text(query_text)
            if q_emb:
                query_keywords = _expand_keywords(query_text)
                ts_query_parts = [f'"{kw}"' if " " in kw else kw for kw in query_keywords]
                ts_query_text = " OR ".join(ts_query_parts) if ts_query_parts else query_text
                db_hits = query_hybrid(ts_query_text, q_emb, k=k * 2)
                if db_hits is not None:
                    matched_events = db_hits
                    db_search_successful = True
        except Exception as e:
            logger.debug(f"retrieve_evidence DB hybrid failed, falling back to local: {e}")

    if not db_search_successful:
        data_path = settings.resolved_data_path
        query_terms = " ".join(_expand_keywords(query_text))
        keyword_hits = search_local_signals(query_terms, data_path, limit=settings.max_events_to_scan)
        vector_hits = []
        if vector_available():
            try:
                q_emb = await embed_text(query_text)
                if q_emb:
                    vector_hits = query_similar(q_emb, k=min(100, settings.max_events_to_scan))
            except Exception as ve:
                logger.debug(f"retrieve_evidence vector search failed: {ve}")
        if keyword_hits is None:
            # Compatibility path for SQLite builds without FTS5.
            events = safe_read_jsonl(data_path, limit=settings.max_events_to_scan, freshness_hours=settings.freshness_hours)
            if not events:
                events = safe_read_jsonl(data_path, limit=settings.max_events_to_scan, freshness_hours=None)
            query_keywords = _expand_keywords(query_text)
            keyword_hits = [event for event in events if any(
                keyword in " ".join(str(event.get(key) or "").lower() for key in ("title", "content", "company"))
                for keyword in query_keywords
            )]
        matched_events = reciprocal_rank_fusion(keyword_hits, vector_hits, limit=k * 10)

    matched_events = filter_by_freshness(query_text, matched_events, settings.freshness_hours)
    matched_events = rerank_results(query_text, matched_events, limit=k)

    return _to_evidence(matched_events)[:k]
