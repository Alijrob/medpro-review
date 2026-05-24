variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "aws_account" {
  description = "AWS account ID"
  type        = string
}

variable "reports_kms_key_arn" {
  description = "KMS key ARN for reports bucket encryption"
  type        = string
}

variable "audit_kms_key_arn" {
  description = "KMS key ARN for WORM audit bucket encryption"
  type        = string
}

variable "audit_retention_years" {
  description = "Object Lock retention period in years for the audit WORM bucket"
  type        = number
  default     = 7
}
