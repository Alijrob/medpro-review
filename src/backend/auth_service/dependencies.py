"""
dependencies.py — FastAPI auth dependencies (the reusable overlay).

These are what every protected route depends on:
  get_current_user                -> verified identity or 401
  require_permissions(*perms)     -> RBAC permission gate or 403
  require_roles(*roles)           -> RBAC role gate or 403
  require_personal_use_certified  -> Path B gate (DECISIONS.md Entry 004) or 403
"""
from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Header, HTTPException, status

from . import store
from .config import AuthSettings, get_settings
from .models import AuthenticatedUser
from .security import AuthError, verify_token

_BEARER = {"WWW-Authenticate": "Bearer"}


def _extract_bearer(authorization: str | None) -> str:
    if not authorization or not authorization.lower().startswith("bearer "):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, "missing bearer token", headers=_BEARER
        )
    token = authorization.split(" ", 1)[1].strip()
    if not token:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "empty bearer token", headers=_BEARER)
    return token


def get_current_user(
    authorization: Annotated[str | None, Header()] = None,
    settings: Annotated[AuthSettings, Depends(get_settings)] = None,
) -> AuthenticatedUser:
    token = _extract_bearer(authorization)
    try:
        claims = verify_token(token)
    except AuthError as exc:
        raise HTTPException(exc.status_code, exc.detail, headers=_BEARER) from exc
    return AuthenticatedUser.from_claims(claims, settings)


CurrentUser = Annotated[AuthenticatedUser, Depends(get_current_user)]


def require_permissions(*required: str):
    def dependency(user: CurrentUser) -> AuthenticatedUser:
        missing = [p for p in required if not user.has_permission(p)]
        if missing:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"missing required permissions: {missing}"
            )
        return user

    return dependency


def require_roles(*roles: str):
    def dependency(user: CurrentUser) -> AuthenticatedUser:
        if not user.has_any_role(*roles):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, f"requires one of roles: {list(roles)}"
            )
        return user

    return dependency


def require_personal_use_certified(user: CurrentUser) -> AuthenticatedUser:
    """Path B gate: the user must have an on-file personal-use-only certification."""
    if store.get_certification(user.sub) is None:
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "personal-use certification required before this action (Path B). "
            "POST /v1/use-agreement first.",
        )
    return user
