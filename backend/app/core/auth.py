from __future__ import annotations

import hashlib
import logging
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..settings import settings

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def _api_key_from_request(request: Optional[Request]) -> Optional[str]:
    """Extract raw API key from the X-API-Key header (bots/CI)."""
    if request is None:
        return None
    try:
        header_key = request.headers.get("x-api-key", "").strip()
        if header_key:
            return header_key
        return None
    except Exception:
        return None


def _verify_api_key(raw_key: str) -> Optional[dict]:
    """Validate SiliconPulse API key (sp_live_...) via sha256 hash lookup."""
    if not raw_key or not raw_key.startswith("sp_live_") or len(raw_key) < 24:
        return None
    try:
        from ..supabase_client import lookup_api_key, touch_api_key

        key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
        row = lookup_api_key(key_hash)
        if not row or not row.get("user_id"):
            return None
        try:
            touch_api_key(row.get("id", ""))
        except Exception:
            pass
        return {"user_id": row["user_id"], "email": None, "via": "api_key", "key_id": row.get("id")}
    except Exception as e:
        logger.debug(f"API key verification failed: {e}")
        return None


def _get_signing_key(token: str):
    if not settings.clerk_issuer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_ISSUER is not configured",
        )

    jwks_client = jwt.PyJWKClient(f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json")
    return jwks_client.get_signing_key_from_jwt(token)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Validate Clerk bearer token (or SiliconPulse API key fallback) and return identity payload."""
    if credentials is None:
        # Bots/CI path: API keys are header-only to keep them out of URLs and logs.
        raw_key = _api_key_from_request(request)
        if raw_key:
            identity = _verify_api_key(raw_key)
            if identity:
                return identity
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid API key",
            )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Authorization header",
        )

    token = credentials.credentials

    try:
        signing_key = _get_signing_key(token)
        decode_args = {
            "jwt": token,
            "key": signing_key.key,
            "algorithms": ["RS256"],
            "issuer": settings.clerk_issuer.rstrip("/"),
        }

        if settings.clerk_audience:
            decode_args["audience"] = settings.clerk_audience
        else:
            decode_args["options"] = {"verify_aud": False}

        payload = jwt.decode(**decode_args)
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {str(exc)}",
        ) from exc

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token payload missing subject (sub)",
        )

    # Extract email from multiple possible JWT claim locations
    email = None
    if "email" in payload:
        email = payload.get("email")
    elif "email_verified" in payload:
        # Some Clerk tokens have email_verified but not email; fetch contextually
        email = payload.get("email")

    # Additional fallback: check primary_email_address_id and related claims
    if not email and "primary_email_address_id" in payload:
        # This is just metadata; actual email is typically in "email" claim
        logger.debug(f"User {user_id} has primary_email_address_id but email not in token")

    logger.info(f"JWT token decoded: user_id={user_id}, email={email}, full_claims={list(payload.keys())}")

    return {
        "user_id": user_id,
        "email": email,
        "session_id": payload.get("sid"),
        "claims": payload,
    }


def require_privileged_role(user: dict, required_role: str | None = None) -> None:
    """Fail closed unless the verified identity carries the configured admin role."""
    role_name = (required_role or settings.privileged_inject_role or "admin").strip().lower()
    claims = user.get("claims") if isinstance(user, dict) else None
    if not isinstance(claims, dict):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Privileged role required")
    metadata = claims.get("public_metadata")
    metadata = metadata if isinstance(metadata, dict) else {}
    roles = claims.get("roles")
    if isinstance(roles, str):
        roles = [roles]
    if not isinstance(roles, list):
        roles = []
    candidates = [claims.get("role"), metadata.get("role"), *roles]
    if not any(isinstance(role, str) and role.strip().lower() == role_name for role in candidates):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Privileged role required")
