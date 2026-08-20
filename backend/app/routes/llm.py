from fastapi import APIRouter, Depends

from ..core.auth import get_current_user
from ..services.gemini_client import gemini_client

router = APIRouter(dependencies=[Depends(get_current_user)])


@router.get("/health")
async def llm_health():
    """Check Gemini configuration health"""
    return await gemini_client.check_health()


@router.get("/models")
async def list_llm_models():
    """List available Gemini models"""
    return gemini_client.list_available_models()
