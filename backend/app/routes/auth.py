import logging

from fastapi import APIRouter, Depends

from ..cache import event_cache
from ..core.auth import get_current_user
from ..demo_generator import DemoGenerator
from ..settings import settings
from ..supabase_client import ensure_user
from ..utils import deduplicate_and_append

router = APIRouter(dependencies=[Depends(get_current_user)])
logger = logging.getLogger(__name__)


@router.get("/me")
async def auth_me(user=Depends(get_current_user)):
    """Sync authenticated user to Supabase and return user identity."""
    user_id = user.get("user_id")
    user_email = user.get("email")

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


@router.post("/bootstrap")
async def bootstrap_system():
    """
    Generate fresh demo events and populate the stream.
    """
    try:
        generator = DemoGenerator()
        new_events = generator.generate_batch(10)

        data_path = settings.resolved_data_path
        added_count = deduplicate_and_append(new_events, data_path)

        event_cache.refresh(data_path)

        return {
            "status": "success",
            "new_events": added_count,
            "message": f"Bootstrapped {added_count} fresh events"
        }
    except Exception as e:
        logger.error(f"Bootstrap Error: {e}")
        return {"status": "error", "new_events": 0, "error": str(e)}
