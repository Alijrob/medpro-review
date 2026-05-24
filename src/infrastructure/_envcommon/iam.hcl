# =============================================================================
# _envcommon/iam.hcl — IAM base roles shared inputs
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/iam"
}

dependency "eks" {
  config_path = "../eks"

  mock_outputs = {
    cluster_oidc_issuer_url = "https://oidc.eks.us-east-1.amazonaws.com/id/MOCK"
    cluster_oidc_provider_arn = "arn:aws:iam::123456789012:oidc-provider/oidc.eks.us-east-1.amazonaws.com/id/MOCK"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

dependency "s3" {
  config_path = "../s3"

  mock_outputs = {
    reports_bucket_arn     = "arn:aws:s3:::mock-reports-bucket"
    audit_worm_bucket_arn  = "arn:aws:s3:::mock-audit-bucket"
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  oidc_provider_arn       = dependency.eks.outputs.cluster_oidc_provider_arn
  oidc_issuer_url         = dependency.eks.outputs.cluster_oidc_issuer_url
  reports_bucket_arn      = dependency.s3.outputs.reports_bucket_arn
  audit_worm_bucket_arn   = dependency.s3.outputs.audit_worm_bucket_arn

  # Application namespaces that get IRSA roles
  app_namespaces = ["api-gateway", "identity", "reports", "workers", "observability"]
}
