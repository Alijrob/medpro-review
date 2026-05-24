# =============================================================================
# ElastiCache Redis Module — medpro-review
# =============================================================================

locals {
  name_prefix = "${var.project}-${var.environment}"
}

resource "aws_security_group" "redis" {
  name        = "${local.name_prefix}-redis-sg"
  description = "Allow Redis access from private subnets"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 6379
    to_port     = 6379
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
    description = "Redis from private subnets"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-redis-sg" }
}

resource "aws_elasticache_subnet_group" "main" {
  name       = "${local.name_prefix}-redis-sg"
  subnet_ids = var.subnet_ids
  tags       = { Name = "${local.name_prefix}-redis-subnet-group" }
}

# Auth token stored in Secrets Manager
resource "random_password" "redis_auth" {
  count   = var.auth_token_enabled ? 1 : 0
  length  = 64
  special = false  # Redis auth token cannot contain special chars
}

resource "aws_secretsmanager_secret" "redis_auth" {
  count       = var.auth_token_enabled ? 1 : 0
  name        = "/${var.project}/${var.environment}/elasticache/auth-token"
  description = "ElastiCache Redis auth token"
  kms_key_id  = var.kms_key_id
  tags        = { Name = "${local.name_prefix}-redis-auth-token" }
}

resource "aws_secretsmanager_secret_version" "redis_auth" {
  count         = var.auth_token_enabled ? 1 : 0
  secret_id     = aws_secretsmanager_secret.redis_auth[0].id
  secret_string = jsonencode({ auth_token = random_password.redis_auth[0].result })
}

resource "aws_elasticache_replication_group" "main" {
  replication_group_id = "${local.name_prefix}-redis"
  description          = "medpro-review Redis cluster (${var.environment})"

  engine               = "redis"
  engine_version       = var.redis_version
  node_type            = var.node_type
  num_cache_clusters   = var.num_cache_nodes
  port                 = 6379

  subnet_group_name  = aws_elasticache_subnet_group.main.name
  security_group_ids = [aws_security_group.redis.id]

  auth_token             = var.auth_token_enabled ? random_password.redis_auth[0].result : null
  at_rest_encryption_enabled = var.at_rest_encryption_enabled
  transit_encryption_enabled = var.transit_encryption_enabled
  kms_key_id             = var.at_rest_encryption_enabled ? var.kms_key_id : null

  automatic_failover_enabled = var.num_cache_nodes > 1
  multi_az_enabled           = var.num_cache_nodes > 1

  maintenance_window       = var.maintenance_window
  snapshot_retention_limit = var.snapshot_retention_limit
  snapshot_window          = var.snapshot_window

  apply_immediately = var.environment == "dev" ? true : false

  tags = { Name = "${local.name_prefix}-redis" }
}
