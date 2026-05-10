"""Authentication primitives.

Two mechanisms coexist:

1. **End-user auth** via Authentik OIDC. The web app obtains an access
   token through the standard Authentik flow and forwards it as a Bearer
   token; we verify the token's signature against Authentik's JWKS, check
   issuer + audience, and resolve / upsert a local `User` row keyed by
   the `sub` claim.

2. **Internal worker auth** via a static shared secret (`X-Internal-Token`).
   This is only acceptable for service-to-service calls inside the cluster;
   it bypasses the user model and grants a `WorkerPrincipal`. See ADR notes
   for why this was chosen over an Authentik service account in Phase 1.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Annotated, Any

import httpx
from brokerapp_db import User
from fastapi import Depends, Header, Request
from jose import jwt
from jose.exceptions import JWTError
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.config import Settings, get_settings
from api.db import get_session
from api.errors import forbidden, unauthorized

_JWKS_CACHE: dict[str, Any] | None = None
_JWKS_CACHE_AT: float = 0.0
_JWKS_TTL = 60 * 30  # 30 minutes


@dataclass
class WorkerPrincipal:
    """Marker for internal worker calls. Has no user identity."""

    name: str = "worker"


async def _load_jwks(settings: Settings) -> dict[str, Any]:
    global _JWKS_CACHE, _JWKS_CACHE_AT
    if _JWKS_CACHE is not None and time.time() - _JWKS_CACHE_AT < _JWKS_TTL:
        return _JWKS_CACHE
    if not settings.authentik_jwks_url:
        raise unauthorized(
            code="auth.misconfigured",
            detail="Authentik JWKS URL is not configured.",
        )
    async with httpx.AsyncClient(timeout=5.0) as client:
        resp = await client.get(settings.authentik_jwks_url)
        resp.raise_for_status()
        _JWKS_CACHE = resp.json()
        _JWKS_CACHE_AT = time.time()
    assert _JWKS_CACHE is not None
    return _JWKS_CACHE


async def _verify_token(token: str, settings: Settings) -> dict[str, Any]:
    """Verify a JWT against Authentik's JWKS and required claims."""
    jwks = await _load_jwks(settings)
    try:
        unverified_header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise unauthorized(code="auth.malformed_token", detail=str(exc)) from exc

    kid = unverified_header.get("kid")
    key = next(
        (k for k in jwks.get("keys", []) if k.get("kid") == kid),
        None,
    )
    if key is None:
        raise unauthorized(
            code="auth.unknown_kid",
            detail="Token signing key not found in JWKS.",
        )

    try:
        claims = jwt.decode(
            token,
            key,
            algorithms=[key.get("alg", "RS256")],
            audience=settings.authentik_audience,
            issuer=settings.authentik_issuer or None,
        )
    except JWTError as exc:
        raise unauthorized(code="auth.invalid_token", detail=str(exc)) from exc
    return claims


async def _upsert_user(claims: dict[str, Any], session: AsyncSession) -> User:
    sub = claims.get("sub")
    email = claims.get("email")
    if not sub or not email:
        raise unauthorized(
            code="auth.missing_claims",
            detail="Token is missing required claims (sub, email).",
        )
    result = await session.execute(
        select(User).where(User.authentik_sub == sub),
    )
    user = result.scalar_one_or_none()
    if user is None:
        user = User(
            authentik_sub=sub,
            email=email,
            display_name=claims.get("name") or claims.get("preferred_username"),
        )
        session.add(user)
        await session.flush()
    else:
        changed = False
        if user.email != email:
            user.email = email
            changed = True
        new_name = claims.get("name") or claims.get("preferred_username")
        if new_name and user.display_name != new_name:
            user.display_name = new_name
            changed = True
        if changed:
            await session.flush()
    return user


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def _extract_bearer(request: Request) -> str | None:
    auth = request.headers.get("authorization")
    if not auth:
        return None
    scheme, _, token = auth.partition(" ")
    if scheme.lower() != "bearer" or not token:
        return None
    return token.strip() or None


async def current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    token = _extract_bearer(request)
    if not token:
        raise unauthorized()
    claims = await _verify_token(token, settings)
    request.state.user_claims = claims
    return await _upsert_user(claims, session)


async def require_admin(
    request: Request,
    user: Annotated[User, Depends(current_user)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> User:
    claims: dict[str, Any] = getattr(request.state, "user_claims", {}) or {}
    groups: list[str] = claims.get("groups", []) or []
    if settings.authentik_admin_group not in groups:
        raise forbidden(code="auth.not_admin", detail="Admin role required.")
    return user


async def require_worker(
    settings: Annotated[Settings, Depends(get_settings)],
    x_internal_token: Annotated[str | None, Header(alias="X-Internal-Token")] = None,
) -> WorkerPrincipal:
    if not settings.internal_token:
        raise forbidden(
            code="auth.internal_disabled",
            detail="Internal-token auth is not configured.",
        )
    if not x_internal_token or x_internal_token != settings.internal_token:
        raise forbidden(
            code="auth.bad_internal_token",
            detail="Invalid or missing X-Internal-Token.",
        )
    return WorkerPrincipal()


__all__ = [
    "WorkerPrincipal",
    "current_user",
    "require_admin",
    "require_worker",
]
