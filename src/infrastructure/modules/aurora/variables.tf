variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "vpc_id" {
  type = string
}

variable "subnet_ids" {
  description = "Database subnet IDs for the Aurora subnet group"
  type        = list(string)
}

variable "kms_key_arn" {
  description = "KMS key ARN for Aurora encryption at rest"
  type        = string
}

variable "postgres_version" {
  description = "Aurora PostgreSQL engine version"
  type        = string
  default     = "15.4"
}

variable "database_name" {
  description = "Initial database name"
  type        = string
  default     = "medpro"
}

variable "master_username" {
  description = "Master DB username"
  type        = string
  default     = "medpro_admin"
}

variable "create_audit_database" {
  description = "Create a dedicated append-only audit database (DECISIONS.md Entry 005)"
  type        = bool
  default     = true
}

variable "audit_database_name" {
  description = "Name for the audit database"
  type        = string
  default     = "medpro_audit"
}

variable "reader_count" {
  description = "Number of reader instances (0 for dev)"
  type        = number
  default     = 0
}

variable "backup_retention_period" {
  description = "Days to retain automated backups"
  type        = number
  default     = 7
}

variable "preferred_backup_window" {
  type    = string
  default = "03:00-04:00"
}

variable "performance_insights_enabled" {
  type    = bool
  default = true
}

variable "deletion_protection" {
  type    = bool
  default = true
}

variable "allowed_cidr_blocks" {
  description = "CIDR blocks allowed to connect to Aurora (typically private subnets)"
  type        = list(string)
  default     = []
}
