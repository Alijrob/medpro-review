variable "project" { type = string }
variable "environment" { type = string }
variable "vpc_id" { type = string }
variable "subnet_ids" { type = list(string) }
variable "kms_key_id" { type = string }
variable "opensearch_version" { type = string; default = "2.11" }
variable "instance_type" { type = string; default = "t3.small.search" }
variable "instance_count" { type = number; default = 2 }
variable "zone_awareness_enabled" { type = bool; default = true }
variable "availability_zone_count" { type = number; default = 2 }
variable "volume_type" { type = string; default = "gp3" }
variable "volume_size_gb" { type = number; default = 20 }
variable "encrypt_at_rest_enabled" { type = bool; default = true }
variable "node_to_node_encryption" { type = bool; default = true }
variable "enforce_https" { type = bool; default = true }
variable "tls_security_policy" { type = string; default = "Policy-Min-TLS-1-2-2019-07" }
variable "fine_grained_access_control_enabled" { type = bool; default = true }
variable "automated_snapshot_start_hour" { type = number; default = 3 }
variable "allowed_cidr_blocks" { type = list(string); default = [] }
variable "aws_account" { type = string }
