# environments/staging/aurora/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/aurora.hcl"
  expose = true
}

# Staging: HA writer + 1 reader
inputs = {
  reader_count        = 1
  deletion_protection = true
}
