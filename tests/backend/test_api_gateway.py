"""
test_api_gateway.py — Phase 1-G API gateway shell behavior tests.

Drives the real ASGI app through TestClient. Reuses the shared auth overlay, so
tokens are signed with an in-test RSA key and the auth service's JWKS fetch is
monkeypatched. Exercises actual behavior: health/readiness, request-id, rate
limiting (429), idempotency replay, the auth+Path B+OPA chain on /v1/reports.

Run:
    PYTHONPATH=src pytest tests/backend/test_api_gateway.py -v
"""
from __future__ import annotations

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk, jwt
from jose.constants import ALGORITHMS

from backend.api_gateway import opa, stores
from backend.api_gateway.app import app
from backend.api_gateway.config import get_settings as gw_settings
from backend.auth_service import security
from backend.auth_service import store as auth_store
from backend.auth_service.config import get_settings as auth_settings

KID = "gw-test-key"
DOMAIN = "medpro-test.us.auth0.com"
ISSUER = f"https://{DOMAIN}/"
AUDIENCE = "https://api.medpro-test/"
ROLES_CLAIM = "https://researchyourdoctor.com/roles"

_KEY = rsa.generate_private_key(public_exponent=65537, key_size=2048)
_PRIVATE_PEM = _KEY.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.PKCS8,
    serialization.NoEncryption(),
).decode()
_PUBLIC_PEM = (
    _KEY.public_key()
    .public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
    .decode()
)


def _public_jwks() -> dict:
    d = jwk.construct(_PUBLIC_PEM, ALGORITHMS.RS256).to_dict()
    d = {k: (v.decode() if isinstance(v, (bytes, bytearray)) else v) for k, v in d.items()}
    d["kid"] = KID
    d.setdefault("use", "sig")
    return {"keys": [d]}


def make_token(sub: str = "auth0|gw", **overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": sub,
        "iat": now,
        "exp": now + 3600,
        "permissions": [],
        ROLES_CLAIM: ["consumer"],
    }
    claims.update(overrides)
    return jwt.encode(claims, _PRIVATE_PEM, algorithm="RS256", headers={"kid": KID})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


client = TestClient(app)


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    monkeypatch.setenv("AUTH0_DOMAIN", DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUDIENCE)
    auth_settings.cache_clear()
    gw_settings.cache_clear()
    security.reset_jwks_cache()
    stores.reset_stores()
    auth_store.clear()
    monkeypatch.setattr(security, "_fetch_jwks", lambda url: _public_jwks())
    yield
    auth_settings.cache_clear()
    gw_settings.cache_clear()
    security.reset_jwks_cache()
    stores.reset_stores()
    auth_store.clear()


def _certify(sub: str) -> None:
    auth_store.record_certification(sub, "tos-v1.0", __import__("datetime").datetime.now())


# ---------------------------------------------------------------------------
class TestHealthAndHeaders:
    def test_healthz(self):
        assert client.get("/healthz").json()["status"] == "ok"

    def test_readyz_ready_when_opa_disabled(self):
        r = client.get("/readyz")
        assert r.status_code == 200
        assert r.json()["ready"] is True

    def test_request_id_generated(self):
        r = client.get("/healthz")
        assert r.headers.get("X-Request-ID")

    def test_request_id_propagated(self):
        r = client.get("/healthz", headers={"X-Request-ID": "abc-123"})
        assert r.headers["X-Request-ID"] == "abc-123"

    def test_security_headers(self):
        r = client.get("/healthz")
        assert r.headers["X-Content-Type-Options"] == "nosniff"
        assert r.headers["X-Frame-Options"] == "DENY"


# ---------------------------------------------------------------------------
class TestAuthOverlayMounted:
    def test_whoami_requires_auth(self):
        assert client.get("/v1/whoami").status_code == 401

    def test_whoami_with_token(self):
        r = client.get("/v1/whoami", headers=_auth(make_token(sub="auth0|x")))
        assert r.status_code == 200
        assert r.json()["sub"] == "auth0|x"


# ---------------------------------------------------------------------------
class TestRateLimit:
    def test_429_after_limit(self, monkeypatch):
        monkeypatch.setenv("RATE_LIMIT_REQUESTS", "3")
        monkeypatch.setenv("RATE_LIMIT_WINDOW_SECONDS", "60")
        gw_settings.cache_clear()
        codes = [client.get("/healthz").status_code for _ in range(4)]
        assert codes[:3] == [200, 200, 200]
        assert codes[3] == 429
        # Retry-After present on the throttled response
        r = client.get("/healthz")
        assert r.status_code == 429
        assert int(r.headers["Retry-After"]) >= 1


# ---------------------------------------------------------------------------
class TestIdempotency:
    def test_replay_returns_cached_response(self):
        sub = "auth0|idem"
        _certify(sub)
        headers = {**_auth(make_token(sub=sub)), "Idempotency-Key": "key-1"}
        first = client.post("/v1/reports", headers=headers)
        assert first.status_code == 202
        assert first.headers.get("Idempotent-Replay") is None

        second = client.post("/v1/reports", headers=headers)
        assert second.status_code == 202
        assert second.headers.get("Idempotent-Replay") == "true"
        # Replay returns the cached body (same request_id as the first response).
        assert second.json()["request_id"] == first.json()["request_id"]


# ---------------------------------------------------------------------------
class TestReportsChain:
    def test_reports_requires_auth(self):
        assert client.post("/v1/reports").status_code == 401

    def test_reports_blocked_without_path_b_certification(self):
        token = make_token(sub="auth0|nocert")
        assert client.post("/v1/reports", headers=_auth(token)).status_code == 403

    def test_reports_accepted_when_certified_and_opa_disabled(self):
        sub = "auth0|ok"
        _certify(sub)
        r = client.post("/v1/reports", headers=_auth(make_token(sub=sub)))
        assert r.status_code == 202
        assert r.json()["accepted"] is True
        assert r.json()["queued_for"] == sub

    def test_reports_denied_by_opa(self, monkeypatch):
        sub = "auth0|deny"
        _certify(sub)
        monkeypatch.setenv("OPA_ENABLED", "true")
        monkeypatch.setenv("OPA_URL", "http://opa.local")
        gw_settings.cache_clear()
        monkeypatch.setattr(opa, "evaluate", lambda settings, doc: False)
        r = client.post("/v1/reports", headers=_auth(make_token(sub=sub)))
        assert r.status_code == 403

    def test_reports_allowed_by_opa(self, monkeypatch):
        sub = "auth0|allow"
        _certify(sub)
        monkeypatch.setenv("OPA_ENABLED", "true")
        monkeypatch.setenv("OPA_URL", "http://opa.local")
        gw_settings.cache_clear()
        monkeypatch.setattr(opa, "evaluate", lambda settings, doc: True)
        r = client.post("/v1/reports", headers=_auth(make_token(sub=sub)))
        assert r.status_code == 202

    def test_reports_opa_unreachable_fails_closed(self, monkeypatch):
        sub = "auth0|unreach"
        _certify(sub)
        monkeypatch.setenv("OPA_ENABLED", "true")
        monkeypatch.setenv("OPA_URL", "http://opa.local")
        gw_settings.cache_clear()

        def _boom(settings, doc):
            raise opa.OpaUnavailable("connection refused")

        monkeypatch.setattr(opa, "evaluate", _boom)
        r = client.post("/v1/reports", headers=_auth(make_token(sub=sub)))
        assert r.status_code == 503
