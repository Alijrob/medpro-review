"""
API Gateway & FastAPI Backend (component C8) — Phase 1-G shell.

The single ingress for the platform API. Mounts the Phase 1-F auth overlay
(backend.auth_service.dependencies), adds request-id propagation, rate limiting,
idempotency, security headers, and an OPA authorization hook (C2 baseline). The
report/search/etc. services sit behind it from Phase 2 onward.
"""
