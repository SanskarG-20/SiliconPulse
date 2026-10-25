"""Shared tenant access checks for service-role Supabase operations."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import Depends, HTTPException

from ..core.auth import get_current_user
from ..supabase_client import get_brief, is_workspace_member


@dataclass(frozen=True)
class TenantAccess:
    user_id: str

    def require_workspace(self, workspace_id: str) -> None:
        if not workspace_id or not self.user_id or not is_workspace_member(self.user_id, workspace_id):
            raise HTTPException(status_code=403, detail="Not a workspace member")

    def require_brief(self, brief_id: str, *, public_allowed: bool = False) -> dict:
        brief = get_brief(brief_id)
        if not brief:
            raise HTTPException(status_code=404, detail="Brief not found")
        if brief.get("user_id") == self.user_id:
            return brief
        if public_allowed and brief.get("is_public") is True:
            return brief
        if public_allowed and not brief.get("is_public", False):
            raise HTTPException(status_code=403, detail="Brief is private")
        raise HTTPException(status_code=403, detail="Not authorized to access this brief")


def get_tenant_access(user=Depends(get_current_user)) -> TenantAccess:
    user_id = user.get("user_id") if isinstance(user, dict) else None
    if not user_id:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return TenantAccess(user_id=user_id)


def require_public_brief(brief_id: str) -> dict:
    brief = get_brief(brief_id)
    if not brief:
        raise HTTPException(status_code=404, detail="Brief not found")
    if brief.get("is_public") is not True:
        raise HTTPException(status_code=403, detail="Brief is private")
    return brief
