import logging
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ..settings import settings

logger = logging.getLogger(__name__)
bearer_scheme = HTTPBearer(auto_error=False)


def _get_signing_key(token: str):
    if not settings.clerk_issuer:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="CLERK_ISSUER is not configured",
        )

    jwks_client = jwt.PyJWKClient(f"{settings.clerk_issuer.rstrip('/')}/.well-known/jwks.json")
    return jwks_client.get_signing_key_from_jwt(token)


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
):
    """Validate Clerk bearer token and return normalized identity payload with email extraction."""
    if credentials is None:
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