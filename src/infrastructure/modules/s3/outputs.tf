output "reports_bucket_id" {
  description = "Reports bucket name"
  value       = aws_s3_bucket.reports.id
}

output "reports_bucket_arn" {
  description = "Reports bucket ARN"
  value       = aws_s3_bucket.reports.arn
}

output "audit_worm_bucket_id" {
  description = "Audit WORM bucket name"
  value       = aws_s3_bucket.audit_worm.id
}

output "audit_worm_bucket_arn" {
  description = "Audit WORM bucket ARN"
  value       = aws_s3_bucket.audit_worm.arn
}

output "access_logs_bucket_id" {
  description = "Access logs bucket name"
  value       = aws_s3_bucket.access_logs.id
}
