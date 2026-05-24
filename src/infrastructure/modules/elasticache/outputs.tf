output "primary_endpoint" {
  description = "Redis primary endpoint"
  value       = aws_elasticache_replication_group.main.primary_endpoint_address
}

output "reader_endpoint" {
  description = "Redis reader endpoint"
  value       = aws_elasticache_replication_group.main.reader_endpoint_address
}

output "port" {
  value = 6379
}

output "security_group_id" {
  value = aws_security_group.redis.id
}

output "auth_token_secret_arn" {
  description = "Secrets Manager ARN for Redis auth token"
  value       = length(aws_secretsmanager_secret.redis_auth) > 0 ? aws_secretsmanager_secret.redis_auth[0].arn : null
}
