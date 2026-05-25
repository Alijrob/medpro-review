package medpro.authz

# =============================================================================
# authz.rego — baseline API authorization (component C2, Phase 1-H)
# =============================================================================
# The api-gateway (C8) consults this policy on every guarded route via its
# OPA sidecar. The decision path the gateway is configured to query
# (GatewaySettings.opa_decision_path) is "v1/data/medpro/authz/allow", which
# resolves to data.medpro.authz.allow below — keep the package + rule name in
# lockstep with that setting.
#
# Input contract (set by src/backend/api_gateway/opa.py::require_authz):
#   {
#     "subject":     "<auth0 sub>",
#     "roles":       ["consumer", ...],     # namespaced roles claim
#     "permissions": ["create:report", ...],# Auth0 permissions / scope fallback
#     "action":      "create",
#     "resource":    "report"
#   }
#
# Default deny. Path B (DECISIONS.md Entry 004) is strictly B2C, so the only
# first-class principal is "consumer"; "admin" is an internal operator scoped to
# the admin surface. Fine-grained "<action>:<resource>" permission grants on the
# token override the role rules.
# =============================================================================

import rego.v1

default allow := false

# Consumers may order a report (Path B: personal research on a provider).
allow if {
	"consumer" in input.roles
	input.action == "create"
	input.resource == "report"
}

# Consumers may read the consumer-facing surfaces.
allow if {
	"consumer" in input.roles
	input.action == "read"
	input.resource in {"report", "provider", "search"}
}

# Scoped token permissions ("create:report") override the role rules.
allow if {
	required := sprintf("%s:%s", [input.action, input.resource])
	required in input.permissions
}

# Internal operators are allowed only within the admin surface.
allow if {
	"admin" in input.roles
	startswith(input.resource, "admin")
}
