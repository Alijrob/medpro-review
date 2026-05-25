package medpro.authz

# opa test src/policy — unit tests for the baseline authorization policy.

import rego.v1

test_consumer_can_create_report if {
	allow with input as {"roles": ["consumer"], "permissions": [], "action": "create", "resource": "report"}
}

test_consumer_can_read_provider if {
	allow with input as {"roles": ["consumer"], "permissions": [], "action": "read", "resource": "provider"}
}

test_anonymous_is_denied if {
	not allow with input as {"roles": [], "permissions": [], "action": "create", "resource": "report"}
}

test_consumer_cannot_delete_report if {
	not allow with input as {"roles": ["consumer"], "permissions": [], "action": "delete", "resource": "report"}
}

test_consumer_cannot_create_unknown_resource if {
	not allow with input as {"roles": ["consumer"], "permissions": [], "action": "create", "resource": "user"}
}

test_scoped_permission_grant_allows if {
	allow with input as {"roles": [], "permissions": ["export:report"], "action": "export", "resource": "report"}
}

test_admin_allowed_on_admin_surface if {
	allow with input as {"roles": ["admin"], "permissions": [], "action": "read", "resource": "admin/users"}
}

test_admin_denied_outside_admin_surface if {
	not allow with input as {"roles": ["admin"], "permissions": [], "action": "delete", "resource": "report"}
}
