# environments/dev/eks/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/eks.hcl"
  expose = true
}

# Dev overrides: public API endpoint (no bastion needed for dev)
inputs = {
  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true
}
