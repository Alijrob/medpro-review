variable "project" {
  description = "Project name"
  type        = string
}

variable "environment" {
  description = "Deployment environment"
  type        = string
}

variable "aws_account" {
  description = "AWS account ID (used in key policies)"
  type        = string
}

variable "keys" {
  description = "Map of KMS keys to create. Key = logical name, value = key config."
  type = map(object({
    description             = string
    deletion_window_in_days = number
    enable_key_rotation     = bool
  }))
}
