variable "project" {
  type = string
}

variable "environment" {
  type = string
}

variable "aws_account" {
  type = string
}

variable "repositories" {
  description = "List of ECR repository names to create"
  type        = list(string)
}

variable "max_tagged_images" {
  description = "Max number of tagged images to retain per repository"
  type        = number
  default     = 30
}

variable "untagged_expiry_days" {
  description = "Days after which untagged images are purged"
  type        = number
  default     = 1
}

variable "scan_on_push" {
  description = "Enable image vulnerability scanning on push"
  type        = bool
  default     = true
}
