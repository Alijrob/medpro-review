# =============================================================================
# Environment Config — production
#
# TODO-Entry-003: Replace all PLACEHOLDER values once DECISIONS.md Entry 003
# (AWS account / region / domain) is resolved.
# =============================================================================

locals {
  environment = "production"

  # TODO-Entry-003: Replace with actual AWS account ID
  aws_account = "PLACEHOLDER-AWS-ACCOUNT-ID"

  aws_region = "us-east-1"

  domain = "researchyourdoctor.com"

  vpc_cidr = "10.2.0.0/16"

  eks_cluster_version     = "1.29"
  aurora_postgres_version = "15.4"
  redis_version           = "7.0"
}
