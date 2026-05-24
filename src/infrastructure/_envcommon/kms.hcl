# =============================================================================
# _envcommon/kms.hcl — KMS keys shared inputs
# One key per data classification tier
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/kms"
}

inputs = {
  # Keys created by this module (one per data type)
  keys = {
    aurora = {
      description             = "medpro-review Aurora PostgreSQL encryption"
      deletion_window_in_days = 30
      enable_key_rotation     = true
    }
    elasticache = {
      description             = "medpro-review ElastiCache Redis encryption"
      deletion_window_in_days = 30
      enable_key_rotation     = true
    }
    s3_reports = {
      description             = "medpro-review S3 reports bucket encryption"
      deletion_window_in_days = 30
      enable_key_rotation     = true
    }
    s3_audit = {
      description             = "medpro-review S3 WORM audit bucket encryption"
      deletion_window_in_days = 30
      enable_key_rotation     = true
    }
    opensearch = {
      description             = "medpro-review OpenSearch domain encryption"
      deletion_window_in_days = 30
      enable_key_rotation     = true
    }
    eks_secrets = {
      description             = "medpro-review EKS secrets envelope encryption"
      deletion_window_in_days = 30
      enable_key_rotation     = true
    }
  }
}
