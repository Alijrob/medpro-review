# environments/production/eks/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/eks.hcl"
  expose = true
}

# Production: larger nodes, no public API endpoint
inputs = {
  cluster_endpoint_public_access = false
  node_groups = {
    system = {
      name           = "system"
      instance_types = ["m5.large"]
      min_size       = 2
      max_size        = 6
      desired_size   = 3
      labels = { role = "system" }
      taints = []
    }
    application = {
      name           = "application"
      instance_types = ["m5.2xlarge"]
      min_size       = 2
      max_size       = 20
      desired_size   = 4
      labels = { role = "application" }
      taints = []
    }
    workers = {
      name           = "workers"
      instance_types = ["c5.4xlarge"]
      min_size       = 0
      max_size       = 40
      desired_size   = 2
      labels = { role = "workers" }
      taints = [{ key = "dedicated", value = "workers", effect = "NO_SCHEDULE" }]
    }
  }
}
