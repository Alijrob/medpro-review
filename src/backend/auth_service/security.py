"""
security.py — Auth0 JWT verification (RS256 via JWKS).

The service validates tokens minted by Auth0; it never issues them (IDaaS, locked
stack — "minimize internal security burden"). JWKS are fetched once and cached
with a TTL; on an unknown `kid` (key rotation) the cache is force-refreshed once
before failing. Verification checks signature, issuer, audience, and expiry.
"""
from __future__ import annotations

import time

import httpx
from jose import jwt
from jose.exceptions import ExpiredSignatureError, JWTClaimsError, JWTError

from .config import get_settings


class AuthError(Exception):
    """Raised on any token/JWKS problem. status_code distinguishes 401 vs 503."""

    def __init__(self, detail: str, status_code: int = 401):
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


# Module-level JWKS cache. Reset in tests via reset_jwks_cache().
_jwks_cache: dict = {"keys": None, "fetched_at": 0.0}


def reset_jwks_cache() -> None:
    _jwks_cache["keys"] = None
    _jwks_cache["fetched_at"] = 0.0


def _fetch_jwks(url: str) -> dict:
    """HTTP GET the JWKS document. Patched in tests to avoid network."""
    resp = httpx.get(url, timeout=5.0)
    resp.raise_for_status()
    return resp.json()


def get_jwks(force: bool = False) -> dict:
    settings = get_settings()
    if not settings.jwks_url:
        raise AuthError("auth provider not configured", status_code=503)
    now = time.time()
    stale = now - _jwks_cache["fetched_at"] > settings.jwks_ttl_seconds
    if force or _jwks_cache["keys"] is None or stale:
        try:
            _jwks_cache["keys"] = _fetch_jwks(settings.jwks_url)
            _jwks_cache["fetched_at"] = now
        except Exception as exc:  # network / JSON / HTTP error
            raise AuthError("could not fetch signing keys", status_code=503) from exc
    return _jwks_cache["keys"]


def _signing_key(token: str) -> dict:
    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise AuthError("malformed token header") from exc
    kid = header.get("kid")
    if not kid:
        raise AuthError("token missing 'kid'")
    for refresh in (False, True):  # retry once with a forced refresh for key rotation
        for key in get_jwks(force=refresh).get("keys", []):
            if key.get("kid") == kid:
                return key
    raise AuthError("no signing key matches token 'kid'")


def verify_token(token: str) -> dict:
    """Verify signature + standard claims and return the decoded claim set."""
    settings = get_settings()
    if not settings.is_configured:
        raise AuthError("auth provider not configured", status_code=503)
    key = _signing_key(token)
    try:
        return jwt.decode(
            token,
            key,
            algorithms=settings.algorithms,
            audience=settings.auth0_audience,
            issuer=settings.issuer,
        )
    except ExpiredSignatureError as exc:
        raise AuthError("token expired") from exc
    except JWTClaimsError as exc:
        raise AuthError(f"invalid claims: {exc}") from exc
    except JWTError as exc:
        raise AuthError("invalid token") from exc
