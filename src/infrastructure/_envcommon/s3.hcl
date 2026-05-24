# =============================================================================
# _envcommon/s3.hcl — S3 buckets shared inputs
#
# Buckets created:
#   1. medpro-review-reports-{env}      — report output files (versioned, KMS-encrypted)
#   2. medpro-review-audit-worm-{env}   — immutable audit archive (Object Lock COMPLIANCE)
#   3. medpro-review-access-logs-{env}  — S3 access logs for the above buckets
#   4. medpro-review-vpc-flow-logs-{env} — VPC flow logs destination
#
# DECISIONS.md Entry 005: QLDB replaced with Aurora append-only + WORM S3.
# The audit-worm bucket enforces WORM via S3 Object Lock in COMPLIANCE mode.
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/s3"
}

dependency "kms" {
  config_path = "../kms"

  mock_outputs = {
    key_arns = {
      s3_reports = "arn:aws:kms:us-east-1:123456789012:key/mock-reports-key"
      s3_audit   = "arn:aws:kms:us-east-1:123456789012:key/mock-audit-key"
    }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  reports_kms_key_arn = dependency.kms.outputs.key_arns["s3_reports"]
  audit_kms_key_arn   = dependency.kms.outputs.key_arns["s3_audit"]

  # Object Lock retention: 7 years for audit records (beyond any legal hold period)
  audit_retention_years = 7
}
