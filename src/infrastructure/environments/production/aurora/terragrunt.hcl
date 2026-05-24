# environments/production/aurora/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/aurora.hcl"
  expose = true
}

# Production: 2 readers, deletion protection on
inputs = {
  reader_count        = 2
  deletion_protection = true
  backup_retention_period = 14
}
