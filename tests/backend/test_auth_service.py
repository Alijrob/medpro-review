"""
test_auth_service.py — Phase 1-F auth service shell behavior tests.

Drives the real FastAPI app through TestClient. Tokens are signed with an in-test
RSA key; the JWKS fetch is monkeypatched to return the matching public key, so no
network or live Auth0 tenant is needed. Tests exercise actual request/response
behavior (status codes, claim parsing, RBAC, Path B gate), not just imports.

Run:
    PYTHONPATH=src pytest tests/backend/ -v
"""
from __future__ import annotations

import time

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from jose import jwk, jwt
from jose.constants import ALGORITHMS

from backend.auth_service import security, store
from backend.auth_service.app import app
from backend.auth_service.config import get_settings

KID = "test-key"
DOMAIN = "medpro-test.us.auth0.com"
ISSUER = f"https://{DOMAIN}/"
AUDIENCE = "https://api.medpro-test/"
ROLES_CLAIM = "https://researchyourdoctor.com/roles"
EMAIL_CLAIM = "https://researchyourdoctor.com/email"

# One RSA keypair for the whole module.
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


def make_token(**overrides) -> str:
    now = int(time.time())
    claims = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "auth0|user-123",
        "iat": now,
        "exp": now + 3600,
        "permissions": [],
        ROLES_CLAIM: [],
        EMAIL_CLAIM: "patient@example.com",
    }
    claims.update(overrides)
    return jwt.encode(claims, _PRIVATE_PEM, algorithm="RS256", headers={"kid": KID})


def _auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


client = TestClient(app)


@pytest.fixture(autouse=True)
def _configured_env(monkeypatch):
    """Configure Auth0 settings, stub JWKS, reset caches/store before each test."""
    monkeypatch.setenv("AUTH0_DOMAIN", DOMAIN)
    monkeypatch.setenv("AUTH0_AUDIENCE", AUDIENCE)
    get_settings.cache_clear()
    security.reset_jwks_cache()
    store.clear()
    monkeypatch.setattr(security, "_fetch_jwks", lambda url: _public_jwks())
    yield
    get_settings.cache_clear()
    security.reset_jwks_cache()
    store.clear()


# ---------------------------------------------------------------------------
class TestHealth:
    def test_healthz_ok(self):
        r = client.get("/healthz")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_readyz_ready_when_configured(self):
        r = client.get("/readyz")
        assert r.status_code == 200
        assert r.json()["ready"] is True

    def test_readyz_not_ready_when_unconfigured(self, monkeypatch):
        monkeypatch.delenv("AUTH0_DOMAIN", raising=False)
        monkeypatch.delenv("AUTH0_AUDIENCE", raising=False)
        get_settings.cache_clear()
        r = client.get("/readyz")
        assert r.status_code == 503
        assert r.json()["ready"] is False


# ---------------------------------------------------------------------------
class TestAuthentication:
    def test_me_requires_token(self):
        assert client.get("/v1/me").status_code == 401

    def test_me_rejects_garbage_token(self):
        assert client.get("/v1/me", headers=_auth("not-a-jwt")).status_code == 401

    def test_me_rejects_non_bearer_scheme(self):
        r = client.get("/v1/me", headers={"Authorization": "Basic abc"})
        assert r.status_code == 401

    def test_me_with_valid_token(self):
        token = make_token(
            sub="auth0|abc",
            permissions=["read:reports"],
            **{ROLES_CLAIM: ["consumer"], EMAIL_CLAIM: "jane@example.com"},
        )
        r = client.get("/v1/me", headers=_auth(token))
        assert r.status_code == 200
        body = r.json()
        assert body["sub"] == "auth0|abc"
        assert body["email"] == "jane@example.com"
        assert body["roles"] == ["consumer"]
        assert "read:reports" in body["permissions"]

    def test_expired_token_rejected(self):
        token = make_token(exp=int(time.time()) - 30)
        assert client.get("/v1/me", headers=_auth(token)).status_code == 401

    def test_wrong_audience_rejected(self):
        token = make_token(aud="https://some-other-api/")
        assert client.get("/v1/me", headers=_auth(token)).status_code == 401

    def test_wrong_issuer_rejected(self):
        token = make_token(iss="https://evil.example.com/")
        assert client.get("/v1/me", headers=_auth(token)).status_code == 401

    def test_unknown_kid_rejected(self):
        token = jwt.encode(
            {"iss": ISSUER, "aud": AUDIENCE, "sub": "x", "exp": int(time.time()) + 60},
            _PRIVATE_PEM,
            algorithm="RS256",
            headers={"kid": "some-other-kid"},
        )
        assert client.get("/v1/me", headers=_auth(token)).status_code == 401


# ---------------------------------------------------------------------------
class TestRbac:
    def test_admin_route_forbidden_for_consumer(self):
        token = make_token(**{ROLES_CLAIM: ["consumer"]})
        assert client.get("/v1/admin/ping", headers=_auth(token)).status_code == 403

    def test_admin_route_allowed_for_admin(self):
        token = make_token(**{ROLES_CLAIM: ["admin"]})
        r = client.get("/v1/admin/ping", headers=_auth(token))
        assert r.status_code == 200
        assert r.json()["pong"] is True


# ---------------------------------------------------------------------------
class TestPathBCertification:
    def test_preflight_blocked_without_certification(self):
        token = make_token(sub="auth0|nocert")
        r = client.get("/v1/reports/preflight", headers=_auth(token))
        assert r.status_code == 403

    def test_use_agreement_rejects_false_certification(self):
        token = make_token(sub="auth0|u1")
        r = client.post(
            "/v1/use-agreement",
            headers=_auth(token),
            json={"tos_version": "tos-v1.0", "certified_personal_use_only": False},
        )
        assert r.status_code == 400

    def test_certify_then_preflight_passes(self):
        token = make_token(sub="auth0|u2")
        rec = client.post(
            "/v1/use-agreement",
            headers=_auth(token),
            json={"tos_version": "tos-v1.0", "certified_personal_use_only": True},
        )
        assert rec.status_code == 200
        body = rec.json()
        assert body["recorded"] is True
        assert body["persisted"] is False  # shell: in-memory only
        assert body["sub"] == "auth0|u2"

        pre = client.get("/v1/reports/preflight", headers=_auth(token))
        assert pre.status_code == 200
        assert pre.json()["eligible"] is True
        assert pre.json()["tos_version"] == "tos-v1.0"

    def test_certification_is_per_user(self):
        # u3 certifies; u4 must still be blocked.
        t3 = make_token(sub="auth0|u3")
        client.post(
            "/v1/use-agreement",
            headers=_auth(t3),
            json={"tos_version": "tos-v1.0", "certified_personal_use_only": True},
        )
        t4 = make_token(sub="auth0|u4")
        assert client.get("/v1/reports/preflight", headers=_auth(t4)).status_code == 403
