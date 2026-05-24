# environments/dev/aurora/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/aurora.hcl"
  expose = true
}

# Dev overrides: minimal cluster, no deletion protection
inputs = {
  deletion_protection     = false
  backup_retention_period = 1
}
