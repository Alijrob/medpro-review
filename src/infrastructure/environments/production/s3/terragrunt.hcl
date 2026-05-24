# environments/production/s3/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/s3.hcl"
  expose = true
}
