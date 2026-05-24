# environments/dev/vpc/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/vpc.hcl"
  expose = true
}

# Dev cost optimization: one NAT gateway instead of one per AZ
inputs = {
  single_nat_gateway = true
}
