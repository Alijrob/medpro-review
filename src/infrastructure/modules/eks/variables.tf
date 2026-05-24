variable "project" { type = string }
variable "environment" { type = string }
variable "aws_account" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "kms_key_arn" { type = string }
variable "cluster_version" { type = string; default = "1.29" }
variable "cluster_endpoint_private_access" { type = bool; default = true }
variable "cluster_endpoint_public_access" { type = bool; default = false }

variable "cluster_enabled_log_types" {
  type    = list(string)
  default = ["api", "audit", "authenticator", "controllerManager", "scheduler"]
}

variable "envelope_encryption_enabled" { type = bool; default = true }

variable "node_groups" {
  description = "Map of managed node group configs"
  type = map(object({
    name           = string
    instance_types = list(string)
    min_size       = number
    max_size       = number
    desired_size   = number
    labels         = map(string)
    taints = list(object({
      key    = string
      value  = string
      effect = string
    }))
  }))
}

variable "addons" {
  description = "EKS add-ons to install"
  type        = map(object({}))
  default = {
    coredns            = {}
    kube-proxy         = {}
    vpc-cni            = {}
    aws-ebs-csi-driver = {}
  }
}
