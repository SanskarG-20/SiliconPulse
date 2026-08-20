from fastapi import APIRouter

from .auth import router as auth_router
from .signals import router as signals_router
from .query import router as query_router
from .sources import router as sources_router
from .export import router as export_router
from .recommendations import router as recommendations_router
from .diagnostics import router as diagnostics_router
from .llm import router as llm_router

router = APIRouter(dependencies=[])
router.include_router(auth_router, prefix="/auth", tags=["auth"])
router.include_router(signals_router, prefix="", tags=["signals"])
router.include_router(query_router, prefix="", tags=["query"])
router.include_router(sources_router, prefix="/sources", tags=["sources"])
router.include_router(export_router, prefix="", tags=["export"])
router.include_router(recommendations_router, prefix="", tags=["recommendations"])
router.include_router(diagnostics_router, prefix="/user", tags=["diagnostics"])
router.include_router(llm_router, prefix="/llm", tags=["llm"])