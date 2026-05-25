"""
opa.py — Open Policy Agent authorization hook (C2 baseline).

The gateway asks OPA "is this subject allowed to perform this action on this
resource?" before forwarding to a downstream service. In the shell OPA is OFF
(opa_enabled=False) and the hook fails OPEN for authenticated users — there is no
opa-sidecar yet. Once C2 ships, opa_enabled flips on and the hook fails CLOSED:
a deny or an unreachable OPA both block the request.
"""
from __future__ import annotations

from typing import Annotated

import httpx
from fastapi import Depends, HTTPException, status

from .config import GatewaySettings, get_settings

# Import the shared auth overlay — this is the whole point of the gateway.
from backend.auth_service.dependencies import get_current_user
from backend.auth_service.models import AuthenticatedUser


class OpaUnavailable(Exception):
    pass


def evaluate(settings: GatewaySettings, input_doc: dict) -> bool:
    """POST the decision input to OPA and return the boolean allow result.

    Patched in tests. Raises OpaUnavailable on any transport/shape problem so the
    caller can fail closed.
    """
    url = f"{settings.opa_url.rstrip('/')}/{settings.opa_decision_path.lstrip('/')}"
    try:
        resp = httpx.post(url, json={"input": input_doc}, timeout=2.0)
        resp.raise_for_status()
        return bool(resp.json().get("result", False))
    except Exception as exc:  # network / HTTP / JSON
        raise OpaUnavailable(str(exc)) from exc


def require_authz(action: str, resource: str):
    """Dependency factory: enforce an OPA allow decision for (action, resource)."""

    def dependency(
        user: Annotated[AuthenticatedUser, Depends(get_current_user)],
        settings: Annotated[GatewaySettings, Depends(get_settings)],
    ) -> AuthenticatedUser:
        if not settings.opa_enabled:
            return user  # baseline: no policy engine yet, allow authenticated users
        input_doc = {
            "subject": user.sub,
            "roles": user.roles,
            "permissions": user.permissions,
            "action": action,
            "resource": resource,
        }
        try:
            allowed = evaluate(settings, input_doc)
        except OpaUnavailable as exc:
            raise HTTPException(
                status.HTTP_503_SERVICE_UNAVAILABLE,
                "authorization service unavailable",
            ) from exc
        if not allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "denied by policy")
        return user

    return dependency
