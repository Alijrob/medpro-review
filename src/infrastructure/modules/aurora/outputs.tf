output "cluster_id" {
  description = "Aurora cluster identifier"
  value       = aws_rds_cluster.main.cluster_identifier
}

output "endpoint" {
  description = "Aurora writer endpoint"
  value       = aws_rds_cluster.main.endpoint
}

output "reader_endpoint" {
  description = "Aurora reader endpoint"
  value       = aws_rds_cluster.main.reader_endpoint
}

output "port" {
  description = "Aurora port"
  value       = aws_rds_cluster.main.port
}

output "database_name" {
  description = "Primary database name"
  value       = aws_rds_cluster.main.database_name
}

output "security_group_id" {
  description = "Aurora security group ID"
  value       = aws_security_group.aurora.id
}

output "credentials_secret_arn" {
  description = "Secrets Manager ARN for master credentials"
  value       = aws_secretsmanager_secret.aurora_master.arn
}

output "cluster_resource_id" {
  description = "Aurora cluster resource ID (used for IAM auth)"
  value       = aws_rds_cluster.main.cluster_resource_id
}
