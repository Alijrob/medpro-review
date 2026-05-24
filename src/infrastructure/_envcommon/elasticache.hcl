# =============================================================================
# _envcommon/elasticache.hcl — ElastiCache Redis shared inputs
#
# Used for: API rate limiting, session cache, provider search results cache,
#           report job queue status, Temporal workflow cache layer
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/elasticache"
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id             = "vpc-mock"
    private_subnet_ids = ["subnet-mock-pa", "subnet-mock-pb", "subnet-mock-pc"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "kms" {
  config_path = "../kms"

  mock_outputs = {
    key_arns = {
      elasticache = "arn:aws:kms:us-east-1:123456789012:key/mock-redis-key"
    }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = dependency.vpc.outputs.private_subnet_ids
  kms_key_id = dependency.kms.outputs.key_arns["elasticache"]

  redis_version     = local.env_vars.locals.redis_version
  node_type         = "cache.t3.medium"
  num_cache_nodes   = 1  # Dev: single node; overridden to replication group in staging/prod

  # Auth token stored in Secrets Manager at:
  # /medpro-review/{env}/elasticache/auth-token
  auth_token_enabled = true

  # Encryption at rest + in transit
  at_rest_encryption_enabled  = true
  transit_encryption_enabled  = true

  # Maintenance window
  maintenance_window = "mon:04:00-mon:05:00"

  # Snapshot
  snapshot_retention_limit = 5
  snapshot_window          = "03:00-04:00"
}
