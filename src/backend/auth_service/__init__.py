"""
Auth & Identity Service (component C7) — Phase 1-F shell.

Validates Auth0-issued JWTs (RS256 via JWKS), exposes the current identity, and
enforces the Path B permissible-use certification at the auth layer. The platform
does NOT issue its own tokens — Auth0 is the IDaaS (DECISIONS.md Entry 002). This
package is the reusable auth overlay; api-gateway (C8, Phase 1-G) mounts the same
dependencies.
"""
