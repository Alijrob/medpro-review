# =============================================================================
# Root Terragrunt Configuration — Medical Professionals Review
#
# All child terragrunt.hcl files include this via:
#   include "root" { path = find_in_parent_folders() }
#
# Remote state is backed by S3 + DynamoDB.
# TODO-Entry-003: Replace bucket/region/account once DECISIONS.md Entry 003 is resolved.
# =============================================================================

locals {
  # Resolve environment-level config (env.hcl in each environments/ENV/ dir)
  env_vars    = read_terragrunt_config(find_in_parent_folders("env.hcl"))
  environment = local.env_vars.locals.environment
  aws_region  = local.env_vars.locals.aws_region
  aws_account = local.env_vars.locals.aws_account
  project     = "medpro-review"

  # Derive the module name from the directory path
  # e.g. environments/dev/vpc -> "vpc"
  module_name = basename(get_terragrunt_dir())
}

# ---------------------------------------------------------------------------
# Remote State — S3 backend
# Bucket: medpro-review-terraform-state-{account}-{region}
# Key:    {project}/{env}/{module}/terraform.tfstate
# ---------------------------------------------------------------------------
remote_state {
  backend = "s3"

  config = {
    # TODO-Entry-003: set bucket name after AWS account assignment
    bucket         = "medpro-review-terraform-state-${local.aws_account}-${local.aws_region}"
    key            = "${local.project}/${local.environment}/${local.module_name}/terraform.tfstate"
    region         = local.aws_region
    encrypt        = true
    dynamodb_table = "medpro-review-terraform-locks"

    # Server-side encryption via KMS
    # TODO-Entry-003: replace placeholder with real KMS ARN after bootstrap
    # kms_key_id = "alias/medpro-review-terraform-state"
  }

  generate = {
    path      = "backend.tf"
    if_exists = "overwrite_terragrunt"
  }
}

# ---------------------------------------------------------------------------
# Generate AWS Provider Block
# ---------------------------------------------------------------------------
generate "provider" {
  path      = "provider.tf"
  if_exists = "overwrite_terragrunt"

  contents = <<-EOF
    terraform {
      required_version = ">= 1.5"

      required_providers {
        aws = {
          source  = "hashicorp/aws"
          version = "~> 5.0"
        }
        random = {
          source  = "hashicorp/random"
          version = "~> 3.5"
        }
      }
    }

    provider "aws" {
      region = "${local.aws_region}"

      default_tags {
        tags = {
          Project     = "medpro-review"
          Environment = "${local.environment}"
          ManagedBy   = "terragrunt"
        }
      }
    }
  EOF
}

# ---------------------------------------------------------------------------
# Shared inputs passed to every module
# ---------------------------------------------------------------------------
inputs = {
  project     = local.project
  environment = local.environment
  aws_region  = local.aws_region
  aws_account = local.aws_account
}
