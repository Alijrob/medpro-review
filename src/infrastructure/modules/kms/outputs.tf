output "key_arns" {
  description = "Map of logical name -> KMS key ARN"
  value       = { for k, v in aws_kms_key.keys : k => v.arn }
}

output "key_ids" {
  description = "Map of logical name -> KMS key ID"
  value       = { for k, v in aws_kms_key.keys : k => v.key_id }
}

output "key_aliases" {
  description = "Map of logical name -> KMS alias ARN"
  value       = { for k, v in aws_kms_alias.keys : k => v.arn }
}
