# environments/staging/elasticache/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/elasticache.hcl"
  expose = true
}

# Staging: replication group (1 primary, 1 replica)
inputs = {
  num_cache_nodes       = 2
  replication_group     = true
}
