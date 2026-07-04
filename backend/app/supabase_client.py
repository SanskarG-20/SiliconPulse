# pyright: reportMissingImports=false
import logging
from typing import Any, Optional

from .settings import settings

logger = logging.getLogger(__name__)

_supabase_client: Optional[Any] = None
_supabase_failed = False


def is_supabase_enabled() -> bool:
    url = (settings.supabase_url or "").strip()
    key = (settings.supabase_service_role_key or "").strip()
    placeholder_tokens = ("your-", "your_", "example", "placeholder")
    if not url or not key:
        return False
    if any(token in url.lower() for token in placeholder_tokens):
        return False
    if any(token in key.lower() for token in placeholder_tokens):
        return False
    return True


def get_supabase_client() -> Optional[Any]:
    global _supabase_client, _supabase_failed

    if _supabase_client is not None:
        return _supabase_client
    if _supabase_failed:
        return None

    if not is_supabase_enabled():
        return None

    try:
        from supabase import create_client
    except Exception as exc:
        logger.warning("Supabase package import failed: %s", exc)
        return None

    try:
        _supabase_client = create_client(
            settings.supabase_url,
            settings.supabase_service_role_key,
        )
        return _supabase_client
    except Exception as exc:
        logger.warning("Supabase client initialization failed: %s", exc)
        _supabase_failed = True
        return None


def ensure_user(user_id: str, email: Optional[str] = None) -> bool:
    """
    Ensure user exists in Supabase. 
    Creates user if not exists, updates email if provided.
    Returns True if successful, False otherwise.
    """
    client = get_supabase_client()
    if client is None:
        logger.warning("Supabase client not initialized - skipping user creation")
        return False

    if not user_id:
        logger.warning("ensure_user called with empty user_id")
        return False

    payload: dict[str, Any] = {"id": user_id}
    if email:
        payload["email"] = email

    try:
        logger.debug(f"Upserting user {user_id} with payload {payload}")
        response = client.table("users").upsert(payload, on_conflict="id").execute()
        
        if response.data:
            logger.info(f"✓ User {user_id} successfully synced to Supabase (email: {email})")
            return True
        else:
            logger.warning(f"Supabase upsert for user {user_id} returned empty data")
            return False
            
    except Exception as exc:
        logger.error(f"✗ Supabase ensure_user failed for {user_id}: {exc}", exc_info=True)
        return False


def insert_query_record(
    user_id: str,
    query_text: str,
    k: int,
    evidence_count: int,
    signal_strength: int,
) -> Optional[str]:
    client = get_supabase_client()
    if client is None:
        return None

    try:
        response = (
            client.table("queries")
            .insert(
                {
                    "user_id": user_id,
                    "query_text": query_text,
                    "k": k,
                    "evidence_count": evidence_count,
                    "signal_strength": signal_strength,
                }
            )
            .execute()
        )

        data = response.data or []
        if data and isinstance(data, list):
            row_id = data[0].get("id")
            if row_id:
                logger.info(f"✓ Query record {row_id} stored for user {user_id}")
                return str(row_id)
        
        logger.warning(f"Query insert returned empty data for user {user_id}")
        return None
    except Exception as exc:
        logger.error(f"✗ Supabase insert_query_record failed for user {user_id}: {exc}", exc_info=True)

    return None


def insert_insight_record(
    user_id: str,
    query_text: str,
    insight: str,
    model_name: str,
    status: str,
    query_id: Optional[str] = None,
) -> Optional[str]:
    client = get_supabase_client()
    if client is None:
        return None

    payload: dict[str, Any] = {
        "user_id": user_id,
        "query_text": query_text,
        "insight": insight,
        "model_name": model_name,
        "status": status,
    }

    if query_id:
        payload["query_id"] = query_id

    try:
        response = client.table("insights").insert(payload).execute()
        data = response.data or []
        if data and isinstance(data, list):
            row_id = data[0].get("id")
            if row_id:
                logger.info(f"✓ Insight record {row_id} stored for user {user_id} (status={status})")
                return str(row_id)
        
        logger.warning(f"Insight insert returned empty data for user {user_id}")
        return None
    except Exception as exc:
        logger.error(f"✗ Supabase insert_insight_record failed for user {user_id}: {exc}", exc_info=True)

    return None


def insert_signal_record(
    user_id: str,
    source: str,
    title: str,
    content: str,
    timestamp: str,
    company: Optional[str] = None,
    event_type: Optional[str] = None,
    url: Optional[str] = None,
) -> Optional[str]:
    client = get_supabase_client()
    if client is None:
        return None

    payload: dict[str, Any] = {
        "user_id": user_id,
        "source": source,
        "title": title,
        "content": content,
        "event_timestamp": timestamp,
        "company": company,
        "event_type": event_type,
        "url": url,
    }

    try:
        response = client.table("signals").insert(payload).execute()
        data = response.data or []
        if data and isinstance(data, list):
            row_id = data[0].get("id")
            if row_id:
                logger.info(f"✓ Signal record {row_id} stored for user {user_id} (source={source})")
                return str(row_id)
        
        logger.warning(f"Signal insert returned empty data for user {user_id}")
        return None
    except Exception as exc:
        logger.error(f"✗ Supabase insert_signal_record failed for user {user_id}: {exc}", exc_info=True)

    return None
