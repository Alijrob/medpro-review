package medpro.redaction

# opa test src/policy — unit tests for the privacy redaction policy.

import rego.v1

_profile := {
	"full_name": "Jane Doe, MD",
	"npi": "1234567890",
	"license_status": "active",
	"disciplinary_actions": [],
	"practice_address": "1 Clinic Way, Springfield",
	"home_address": "12 Private Lane, Springfield",
	"personal_phone": "555-0100",
}

test_consumer_redacts_home_address if {
	"home_address" in redact with input as {"audience": "consumer", "profile": _profile}
}

test_consumer_redacts_personal_phone if {
	"personal_phone" in redact with input as {"audience": "consumer", "profile": _profile}
}

test_consumer_keeps_license_status if {
	not "license_status" in redact with input as {"audience": "consumer", "profile": _profile}
}

test_consumer_keeps_practice_address if {
	not "practice_address" in redact with input as {"audience": "consumer", "profile": _profile}
}

test_redacted_doc_drops_personal_keeps_professional if {
	out := redacted with input as {"audience": "consumer", "profile": _profile}
	not out.home_address
	not out.personal_phone
	out.npi == "1234567890"
	out.practice_address == "1 Clinic Way, Springfield"
}

test_absent_personal_field_not_in_redact_set if {
	# ssn is in consumer_suppressed but absent from the profile -> not redacted
	not "ssn" in redact with input as {"audience": "consumer", "profile": _profile}
}

test_provider_self_sees_everything if {
	count(redact) == 0 with input as {"audience": "provider_self", "profile": _profile}
}

test_internal_sees_everything if {
	out := redacted with input as {"audience": "internal", "profile": _profile}
	out.home_address == "12 Private Lane, Springfield"
}
