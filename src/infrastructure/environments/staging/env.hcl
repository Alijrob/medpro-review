# =============================================================================
# Environment Config — staging
#
# TODO-Entry-003: Replace all PLACEHOLDER values once DECISIONS.md Entry 003
# (AWS account / region / domain) is resolved.
# =============================================================================

locals {
  environment = "staging"

  # TODO-Entry-003: Replace with actual AWS account ID
  aws_account = "PLACEHOLDER-AWS-ACCOUNT-ID"

  # TODO-Entry-003: Replace with selected region
  aws_region = "PLACEHOLDER-AWS-REGION"

  # TODO-Entry-003: Replace with actual domain
  domain = "PLACEHOLDER-DOMAIN"

  vpc_cidr = "10.1.0.0/16"

  eks_cluster_version     = "1.29"
  aurora_postgres_version = "15.4"
  redis_version           = "7.0"
}
