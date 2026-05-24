# =============================================================================
# _envcommon/ecr.hcl — ECR repositories shared inputs
# =============================================================================

locals {
  env_vars = read_terragrunt_config(find_in_parent_folders("env.hcl"))
}

terraform {
  source = "${get_repo_root()}/src/infrastructure/modules/ecr"
}

inputs = {
  # One repository per deployable service
  repositories = [
    "api-gateway",          # C8 — FastAPI API gateway
    "identity-resolver",    # C12 — Identity resolution engine
    "normalization-worker", # C11 — Normalization layer
    "entity-linker",        # C13 — Entity linking & merge
    "report-generator",     # C17 — Report generation service
    "source-adapter",       # C10 — Source adapter workers (shared image)
    "source-health-monitor",# C24 — Source health monitor
    "data-quality",         # C25 — Data quality service
    "dispute-worker",       # C20 — Dispute workflow worker
    "notifications",        # C22 — Notifications service
    "audit-writer",         # C5-audit — Audit ledger writer
    "opa-sidecar",          # C2 — OPA policy engine sidecar
  ]

  # Lifecycle policy: keep last 30 tagged images, untagged purged after 1 day
  max_tagged_images  = 30
  untagged_expiry_days = 1

  # Image scanning on every push
  scan_on_push = true
}
