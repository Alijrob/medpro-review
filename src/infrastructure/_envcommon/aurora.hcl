# =============================================================================
# _envcommon/aurora.hcl — Aurora PostgreSQL shared inputs
#
# Cluster design:
#   - Aurora PostgreSQL 15 (Serverless v2 for dev, provisioned for staging/prod)
#   - 1 writer + 1 reader (dev), 1 writer + 2 readers (staging/prod)
#   - Encryption at rest with KMS
#   - Secrets Manager for credentials (rotated every 30 days)
#   - append_only_audit database for the audit ledger (DECISIONS.md Entry 005)
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/aurora"
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id               = "vpc-mock"
    database_subnet_ids  = ["subnet-mock-a", "subnet-mock-b", "subnet-mock-c"]
    private_subnet_ids   = ["subnet-mock-pa", "subnet-mock-pb", "subnet-mock-pc"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "kms" {
  config_path = "../kms"

  mock_outputs = {
    key_arns = {
      aurora = "arn:aws:kms:us-east-1:123456789012:key/mock-aurora-key"
    }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  vpc_id             = dependency.vpc.outputs.vpc_id
  subnet_ids         = dependency.vpc.outputs.database_subnet_ids
  kms_key_arn        = dependency.kms.outputs.key_arns["aurora"]

  postgres_version       = local.env_vars.locals.aurora_postgres_version
  database_name          = "medpro"

  # Credentials stored in Secrets Manager
  # module generates random password and stores it at:
  # /medpro-review/{env}/aurora/master-credentials
  master_username = "medpro_admin"

  # Enable audit database for append-only audit ledger (Entry 005)
  create_audit_database = true
  audit_database_name   = "medpro_audit"

  # Backup
  backup_retention_period = 7
  preferred_backup_window = "03:00-04:00"

  # Performance Insights
  performance_insights_enabled = true

  # Deletion protection (overridden to false in dev for clean teardown)
  deletion_protection = false
}
