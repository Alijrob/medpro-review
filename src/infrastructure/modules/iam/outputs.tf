output "app_role_arns" {
  description = "Map of namespace -> IRSA role ARN"
  value       = { for k, v in aws_iam_role.app_roles : k => v.arn }
}

output "audit_writer_policy_arn" {
  value = aws_iam_policy.audit_writer.arn
}

output "secrets_read_policy_arn" {
  value = aws_iam_policy.secrets_read.arn
}

output "reports_rw_policy_arn" {
  value = aws_iam_policy.reports_rw.arn
}
