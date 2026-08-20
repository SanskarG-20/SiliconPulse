from fastapi import APIRouter, Depends

from ..core.auth import get_current_user
from ..supabase_client import get_supabase_client

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/diagnostics")
async def user_diagnostics(user=Depends(get_current_user)):
    """Returns the latest user data stored in Supabase."""
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
        user_response = client.table("users").select("*").eq("id", user_id).single().execute()
        user_record = user_response.data if user_response.data else None

        queries_response = client.table("queries").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
        queries = queries_response.data or []

        insights_response = client.table("insights").select("*").eq("user_id", user_id).order("created_at", desc=True).limit(5).execute()
        insights = insights_response.data or []

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
            "recent_insights": insights[:3],
            "recent_signals": signals[:3],
            "message": "All user data from Supabase"
        }
    except Exception as exc:
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f"Diagnostics failed for user {user_id}: {exc}", exc_info=True)
        return {
            "status": "error",
            "user_id": user_id,
            "message": f"Failed to fetch user data: {str(exc)}"
        }