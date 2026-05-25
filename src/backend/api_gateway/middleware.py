"""
middleware.py — gateway cross-cutting middleware.

  RequestIDMiddleware    propagate/generate X-Request-ID
  RateLimitMiddleware    fixed-window rate limit -> 429 + Retry-After
  IdempotencyMiddleware  replay 2xx responses for repeated Idempotency-Key
  SecurityHeadersMiddleware  standard hardening headers

Stores are in-memory in the shell (see stores.py); swapped for Redis in deploy.
"""
from __future__ import annotations

import json
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from .config import get_settings
from .stores import idempotency_store, rate_limiter

REQUEST_ID_HEADER = "X-Request-ID"
IDEMPOTENCY_HEADER = "Idempotency-Key"
_IDEMPOTENT_METHODS = {"POST", "PUT", "PATCH"}


class RequestIDMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault(
            "Strict-Transport-Security", "max-age=31536000; includeSubDomains"
        )
        return response


class RateLimitMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        if not settings.rate_limit_enabled:
            return await call_next(request)
        client_id = request.client.host if request.client else "unknown"
        allowed, retry_after = rate_limiter.check(
            client_id, settings.rate_limit_requests, settings.rate_limit_window_seconds
        )
        if not allowed:
            return JSONResponse(
                {"detail": "rate limit exceeded"},
                status_code=429,
                headers={"Retry-After": str(retry_after)},
            )
        return await call_next(request)


class IdempotencyMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        settings = get_settings()
        key = request.headers.get(IDEMPOTENCY_HEADER)
        if (
            not settings.idempotency_enabled
            or request.method not in _IDEMPOTENT_METHODS
            or not key
        ):
            return await call_next(request)

        cache_key = f"{request.method}:{request.url.path}:{key}"
        cached = idempotency_store.get(cache_key)
        if cached is not None:
            return JSONResponse(
                cached["body"],
                status_code=cached["status"],
                headers={"Idempotent-Replay": "true"},
            )

        response = await call_next(request)
        body = b"".join([chunk async for chunk in response.body_iterator])

        if 200 <= response.status_code < 300:
            try:
                parsed = json.loads(body) if body else None
            except json.JSONDecodeError:
                parsed = None
            if parsed is not None:
                idempotency_store.set(
                    cache_key,
                    {"status": response.status_code, "body": parsed},
                    settings.idempotency_ttl_seconds,
                )

        return Response(
            content=body,
            status_code=response.status_code,
            headers=dict(response.headers),
            media_type=response.media_type,
        )
