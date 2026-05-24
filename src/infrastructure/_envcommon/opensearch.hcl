# =============================================================================
# _envcommon/opensearch.hcl — OpenSearch shared inputs
#
# Used by: C14 (Provider Search Service) — fast provider name + specialty search
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/opensearch"
}

dependency "vpc" {
  config_path = "../vpc"

  mock_outputs = {
    vpc_id             = "vpc-mock"
    private_subnet_ids = ["subnet-mock-pa", "subnet-mock-pb"]
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "kms" {
  config_path = "../kms"

  mock_outputs = {
    key_arns = {
      opensearch = "arn:aws:kms:us-east-1:123456789012:key/mock-os-key"
    }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  vpc_id     = dependency.vpc.outputs.vpc_id
  subnet_ids = slice(dependency.vpc.outputs.private_subnet_ids, 0, 2)
  kms_key_id = dependency.kms.outputs.key_arns["opensearch"]

  # OpenSearch 2.x
  opensearch_version = "2.11"

  # Dev: 2 data nodes (t3.small.search) — staging/prod overrides to larger
  instance_type  = "t3.small.search"
  instance_count = 2

  # Zone awareness for HA across 2 AZs
  zone_awareness_enabled     = true
  availability_zone_count    = 2

  # Storage
  volume_type    = "gp3"
  volume_size_gb = 20

  # Encryption
  encrypt_at_rest_enabled      = true
  node_to_node_encryption      = true
  enforce_https                = true
  tls_security_policy          = "Policy-Min-TLS-1-2-2019-07"

  # Fine-grained access control (internal user DB)
  # TODO: Replace with SAML/Cognito once identity is resolved
  fine_grained_access_control_enabled = true

  # Automated snapshot
  automated_snapshot_start_hour = 3
}
