"""Team workspaces: invite codes, shared watchlist, shared briefs (Phase 3.2)."""
import logging
import secrets

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from ..core.auth import get_current_user
from ..core.tenant import TenantAccess, get_tenant_access
from ..supabase_client import (
    add_workspace_company,
    create_workspace,
    ensure_user,
    is_supabase_enabled,
    join_workspace,
    leave_workspace,
    list_workspace_briefs,
    list_workspace_members,
    list_workspace_watchlist,
    list_workspaces,
    remove_workspace_company,
)

logger = logging.getLogger(__name__)

router = APIRouter(dependencies=[Depends(get_current_user)])


class WorkspaceCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class WorkspaceJoin(BaseModel):
    invite_code: str = Field(..., min_length=4, max_length=32)


class WorkspaceCompanyAdd(BaseModel):
    company: str = Field(..., min_length=1, max_length=100)


def _require_supabase():
    if not is_supabase_enabled():
        raise HTTPException(status_code=503, detail="Workspaces unavailable (persistence not configured)")


@router.get("/workspaces")
async def my_workspaces(user=Depends(get_current_user)):
    return {"workspaces": list_workspaces(user.get("user_id", "")), "persisted": is_supabase_enabled()}


@router.post("/workspaces")
async def create_ws(body: WorkspaceCreate, user=Depends(get_current_user)):
    _require_supabase()
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ensure_user(user_id, user.get("email"))
    for _ in range(3):
        code = secrets.token_hex(4)
        ws = create_workspace(user_id, body.name.strip(), code)
        if ws:
            return {"workspace": ws, "invite_code": code}
    raise HTTPException(status_code=500, detail="Failed to create workspace")


@router.post("/workspaces/join")
async def join_ws(body: WorkspaceJoin, user=Depends(get_current_user)):
    _require_supabase()
    user_id = user.get("user_id")
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    ensure_user(user_id, user.get("email"))
    ws = join_workspace(user_id, body.invite_code.strip())
    if not ws:
        raise HTTPException(status_code=404, detail="Invalid invite code")
    return {"workspace": ws}


@router.get("/workspaces/{workspace_id}")
async def workspace_detail(workspace_id: str, user=Depends(get_current_user), access: TenantAccess = Depends(get_tenant_access)):
    access.require_workspace(workspace_id)
    return {
        "members": list_workspace_members(workspace_id),
        "watchlist": list_workspace_watchlist(workspace_id),
        "briefs": list_workspace_briefs(workspace_id),
    }


@router.post("/workspaces/{workspace_id}/watchlist")
async def workspace_watch_add(workspace_id: str, body: WorkspaceCompanyAdd, user=Depends(get_current_user), access: TenantAccess = Depends(get_tenant_access)):
    user_id = access.user_id
    access.require_workspace(workspace_id)
    add_workspace_company(workspace_id, body.company.strip(), added_by=user_id)
    return {"watchlist": list_workspace_watchlist(workspace_id)}


@router.delete("/workspaces/{workspace_id}/watchlist/{company}")
async def workspace_watch_remove(workspace_id: str, company: str, user=Depends(get_current_user), access: TenantAccess = Depends(get_tenant_access)):
    access.require_workspace(workspace_id)
    remove_workspace_company(workspace_id, company)
    return {"watchlist": list_workspace_watchlist(workspace_id)}


@router.post("/workspaces/{workspace_id}/leave")
async def workspace_leave(workspace_id: str, access: TenantAccess = Depends(get_tenant_access)):
    access.require_workspace(workspace_id)
    leave_workspace(access.user_id, workspace_id)
    return {"left": workspace_id}
