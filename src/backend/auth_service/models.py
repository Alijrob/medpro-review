"""
models.py — request-scoped identity + Path B certification payloads.

AuthenticatedUser is built from validated token claims; it is NOT the canonical
User record (src/schema/v1/users.py). Provisioning the canonical User in Aurora
from `sub` is a later step (needs DATABASE_URL); the shell stays stateless except
for the in-memory certification store.
"""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .config import AuthSettings


class AuthenticatedUser(BaseModel):
    """Identity derived from a verified Auth0 access token."""

    model_config = ConfigDict(frozen=True)

    sub: str = Field(..., description="Auth0 subject claim — the stable external user id.")
    email: str | None = None
    roles: list[str] = Field(default_factory=list)
    permissions: list[str] = Field(default_factory=list)

    def has_permission(self, permission: str) -> bool:
        return permission in self.permissions

    def has_any_role(self, *roles: str) -> bool:
        wanted = {r.value if hasattr(r, "value") else str(r) for r in roles}
        return bool(wanted & set(self.roles))

    @classmethod
    def from_claims(cls, claims: dict, settings: AuthSettings) -> "AuthenticatedUser":
        permissions = list(claims.get(settings.permissions_claim) or [])
        # Fall back to the OAuth2 `scope` string if RBAC permissions are absent.
        if not permissions and isinstance(claims.get("scope"), str):
            permissions = claims["scope"].split()
        roles = list(claims.get(settings.roles_claim) or [])
        email = claims.get(settings.email_claim) or claims.get("email")
        return cls(sub=claims["sub"], email=email, roles=roles, permissions=permissions)


class UseAgreementRequest(BaseModel):
    """Path B certification posted when the user accepts the ToS (at signup/checkout)."""

    tos_version: str = Field(..., max_length=20, examples=["tos-v1.0"])
    certified_personal_use_only: bool = Field(
        ...,
        description="Must be True — personal research only (DECISIONS.md Entry 004).",
    )


class UseAgreementResponse(BaseModel):
    recorded: bool
    agreement_id: UUID
    sub: str
    tos_version: str
    agreed_at: datetime
    persisted: bool = Field(
        default=False,
        description="False in the shell — recorded in-memory only until DATABASE_URL is wired.",
    )
