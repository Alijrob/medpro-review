# environments/production/elasticache/terragrunt.hcl
include "root" {
  path = find_in_parent_folders()
}

include "envcommon" {
  path   = "${get_repo_root()}/src/infrastructure/_envcommon/elasticache.hcl"
  expose = true
}

# Production: replication group (1 primary, 2 replicas)
inputs = {
  num_cache_nodes       = 3
  replication_group     = true
  node_type             = "cache.r6g.large"
}
