# =============================================================================
# Environment Config — dev
#
# TODO-Entry-003: Replace all PLACEHOLDER values once DECISIONS.md Entry 003
# (AWS account / region / domain) is resolved.
# =============================================================================

locals {
  environment = "dev"

  # TODO-Entry-003: Replace with actual AWS account ID
  aws_account = "PLACEHOLDER-AWS-ACCOUNT-ID"

  # TODO-Entry-003: Replace with selected region (e.g. "us-east-1")
  aws_region = "PLACEHOLDER-AWS-REGION"

  domain = "researchyourdoctor.com"

  # CIDR blocks for this environment
  vpc_cidr = "10.0.0.0/16"

  # EKS cluster version
  eks_cluster_version = "1.29"

  # Aurora PostgreSQL version
  aurora_postgres_version = "15.4"

  # ElastiCache Redis version
  redis_version = "7.0"
}
