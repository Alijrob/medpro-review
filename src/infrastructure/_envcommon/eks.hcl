# =============================================================================
# _envcommon/eks.hcl — EKS cluster shared inputs
#
# Cluster design:
#   - Private API endpoint (no public access by default)
#   - IRSA enabled via OIDC provider
#   - 3 managed node groups: system, application, workers
#   - Control plane logging: api, audit, authenticator, controllerManager, scheduler
#   - Cluster add-ons: coredns, kube-proxy, vpc-cni, aws-ebs-csi-driver
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/eks"
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
      eks_secrets = "arn:aws:kms:us-east-1:123456789012:key/mock-eks-key"
    }
  }
  mock_outputs_allowed_terraform_commands = ["validate", "plan"]
}

inputs = {
  vpc_id          = dependency.vpc.outputs.vpc_id
  subnet_ids      = dependency.vpc.outputs.private_subnet_ids
  kms_key_arn     = dependency.kms.outputs.key_arns["eks_secrets"]

  cluster_version = local.env_vars.locals.eks_cluster_version

  # API endpoint access — private only (bastion or VPN required)
  cluster_endpoint_private_access = true
  cluster_endpoint_public_access  = false

  # Control plane logging
  cluster_enabled_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]

  # Envelope encryption for Kubernetes secrets
  envelope_encryption_enabled = true

  # Managed node groups
  node_groups = {
    system = {
      name           = "system"
      instance_types = ["t3.medium"]
      min_size       = 1
      max_size       = 3
      desired_size   = 2
      labels = {
        role = "system"
      }
      taints = []
    }
    application = {
      name           = "application"
      instance_types = ["t3.xlarge"]
      min_size       = 1
      max_size       = 10
      desired_size   = 2
      labels = {
        role = "application"
      }
      taints = []
    }
    workers = {
      name           = "workers"
      instance_types = ["c5.2xlarge"]
      min_size       = 0
      max_size       = 20
      desired_size   = 1
      labels = {
        role = "workers"
      }
      taints = [
        {
          key    = "dedicated"
          value  = "workers"
          effect = "NO_SCHEDULE"
        }
      ]
    }
  }

  # EKS add-ons (latest compatible versions resolved at apply time)
  addons = {
    coredns                = {}
    kube-proxy             = {}
    vpc-cni                = {}
    aws-ebs-csi-driver     = {}
  }
}
