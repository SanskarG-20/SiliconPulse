from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException

from ..core.auth import get_current_user
from ..models import InjectRequest, InjectResponse
from ..settings import settings
from ..supabase_client import ensure_user, insert_signal_record
from ..utils import deduplicate_and_append, safe_read_jsonl

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/signals")
async def get_signals():
    """Get latest signals for the ticker."""
    try:
        data_path = settings.resolved_data_path
        if not data_path.exists():
            return []

        events = safe_read_jsonl(
            data_path,
            limit=20,
            freshness_hours=settings.freshness_hours
        )

        return events
    except Exception as e:
        print(f"Signals Error: {e}")
        return []


@router.post("/inject", response_model=InjectResponse)
async def inject_signal(request: InjectRequest, user=Depends(get_current_user)):
    """
    Inject a new data item into the stream.

    - Accepts InjectRequest with title, content, optional timestamp and source
    - Checks for duplicates using event fingerprint
    - Appends as JSON line to DATA_STREAM_PATH if unique
    """
    try:
        if request.timestamp is None:
            injected_at = datetime.now().isoformat()
        else:
            injected_at = request.timestamp

        data_entry = {
            "title": request.title,
            "content": request.content,
            "timestamp": injected_at,
            "source": request.source
        }

        data_path = settings.resolved_data_path
        added_count = deduplicate_and_append([data_entry], data_path)

        if added_count == 0:
            raise HTTPException(
                status_code=409,
                detail="Duplicate signal: already exists in stream"
            )

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
