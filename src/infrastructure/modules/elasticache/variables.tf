variable "project" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "kms_key_id" { type = string }
variable "redis_version" { type = string; default = "7.0" }
variable "node_type" { type = string; default = "cache.t3.medium" }
variable "num_cache_nodes" { type = number; default = 1 }

variable "replication_group" {
  description = "Create a replication group (true for staging/prod)"
  type        = bool
  default     = false
}

variable "auth_token_enabled" { type = bool; default = true }
variable "at_rest_encryption_enabled" { type = bool; default = true }
variable "transit_encryption_enabled" { type = bool; default = true }
variable "maintenance_window" { type = string; default = "mon:04:00-mon:05:00" }
variable "snapshot_retention_limit" { type = number; default = 5 }
variable "snapshot_window" { type = string; default = "03:00-04:00" }

variable "allowed_cidr_blocks" {
  description = "CIDRs allowed to connect to Redis (typically private subnets)"
  type        = list(string)
  default     = []
}
