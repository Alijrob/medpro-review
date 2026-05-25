package medpro.redaction

# =============================================================================
# redaction.rego — privacy redaction policy (component C2, Phase 1-H)
# =============================================================================
# DECISIONS.md Entry 007: OPA retains a privacy-redaction responsibility under
# Path B — "suppress physician home address from consumer-facing report output."
# This policy generalizes that: it names the personal-PII fields that must never
# appear in consumer output, and exposes both the redaction field set and a
# convenience redacted document.
#
# It is the Report Generation Service (C17, Phase 2) that will call this policy
# when rendering a consumer report; it is shipped now as part of the baseline
# bundle so the policy contract exists and is tested before C17 lands.
#
# Input contract:
#   {
#     "audience": "consumer" | "provider_self" | "internal",
#     "profile":  { ... canonical provider profile fields ... }
#   }
#
# Public-record professional data (license, NPI, disciplinary actions, practice
# address) is always retained — the whole product is built on it. Only personal
# PII with no bearing on a research decision is suppressed for consumers.
# =============================================================================

import rego.v1

# Personal fields never shown to a consumer audience.
consumer_suppressed := {
	"home_address",
	"personal_phone",
	"personal_email",
	"date_of_birth",
	"ssn",
}

# The set of profile keys to redact for the current audience.
# provider_self (CCPA portal, C22) and internal audiences see everything.
redact contains field if {
	input.audience == "consumer"
	some field in consumer_suppressed
	_present(field)
}

_present(field) if {
	input.profile[field]
}

# Convenience: the input profile with the redacted keys removed.
redacted := obj if {
	obj := {k: v |
		some k, v in input.profile
		not k in redact
	}
}
