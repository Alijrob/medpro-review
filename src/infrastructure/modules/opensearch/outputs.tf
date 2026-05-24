output "domain_endpoint" {
  value = aws_opensearch_domain.main.endpoint
}

output "domain_arn" {
  value = aws_opensearch_domain.main.arn
}

output "security_group_id" {
  value = aws_security_group.opensearch.id
}

output "master_password_secret_arn" {
  value = aws_secretsmanager_secret.opensearch_master.arn
}
