# =============================================================================
# _envcommon/vpc.hcl — Shared VPC inputs across all environments
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/vpc"
}

inputs = {
  vpc_cidr = local.env_vars.locals.vpc_cidr

  # 3 Availability Zones for HA
  # TODO-Entry-003: Derive from aws_region once region is locked
  availability_zones = [
    "${local.env_vars.locals.aws_region}a",
    "${local.env_vars.locals.aws_region}b",
    "${local.env_vars.locals.aws_region}c",
  ]

  # Subnets: /20 each (4096 IPs per AZ per tier)
  public_subnet_cidrs  = ["10.0.0.0/20", "10.0.16.0/20", "10.0.32.0/20"]
  private_subnet_cidrs = ["10.0.48.0/20", "10.0.64.0/20", "10.0.80.0/20"]
  database_subnet_cidrs = ["10.0.96.0/24", "10.0.97.0/24", "10.0.98.0/24"]

  # One NAT gateway per AZ (HA mode)
  # Use single_nat_gateway = true to reduce cost in dev (overridable per env)
  single_nat_gateway = false

  # VPC Flow Logs
  enable_flow_logs = true
  flow_log_destination_type = "s3"
}
