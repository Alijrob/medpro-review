variable "project" { type = string }
variable "environment" { type = string }
variable "aws_account" { type = string }
variable "oidc_provider_arn" { type = string }
variable "oidc_issuer_url" { type = string }
variable "reports_bucket_arn" { type = string }
variable "audit_worm_bucket_arn" { type = string }

variable "app_namespaces" {
  description = "K8s namespaces that get IRSA roles"
  type        = list(string)
  default     = ["api-gateway", "identity", "reports", "workers", "observability"]
}
