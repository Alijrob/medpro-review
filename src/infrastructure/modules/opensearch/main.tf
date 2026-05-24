# =============================================================================
# OpenSearch Module — medpro-review
# Used by C14 (Provider Search Service)
# =============================================================================

locals {
  name_prefix   = "${var.project}-${var.environment}"
  domain_name   = "${var.project}-${var.environment}"
  master_password_secret_name = "/${var.project}/${var.environment}/opensearch/master-password"
}

resource "aws_security_group" "opensearch" {
  name        = "${local.name_prefix}-opensearch-sg"
  description = "OpenSearch domain access"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
    description = "HTTPS from private subnets"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${local.name_prefix}-opensearch-sg" }
}

resource "random_password" "opensearch_master" {
  length           = 16
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
  min_upper        = 1
  min_lower        = 1
  min_numeric      = 1
  min_special      = 1
}

resource "aws_secretsmanager_secret" "opensearch_master" {
  name        = local.master_password_secret_name
  description = "OpenSearch master user password"
  kms_key_id  = var.kms_key_id
  tags        = { Name = "${local.name_prefix}-opensearch-master-pw" }
}

resource "aws_secretsmanager_secret_version" "opensearch_master" {
  secret_id     = aws_secretsmanager_secret.opensearch_master.id
  secret_string = jsonencode({ username = "admin", password = random_password.opensearch_master.result })
}

resource "aws_opensearch_domain" "main" {
  domain_name    = local.domain_name
  engine_version = "OpenSearch_${var.opensearch_version}"

  cluster_config {
    instance_type  = var.instance_type
    instance_count = var.instance_count

    zone_awareness_enabled = var.zone_awareness_enabled

    dynamic "zone_awareness_config" {
      for_each = var.zone_awareness_enabled ? [1] : []
      content {
        availability_zone_count = var.availability_zone_count
      }
    }
  }

  vpc_options {
    subnet_ids         = var.subnet_ids
    security_group_ids = [aws_security_group.opensearch.id]
  }

  ebs_options {
    ebs_enabled = true
    volume_type = var.volume_type
    volume_size = var.volume_size_gb
  }

  encrypt_at_rest {
    enabled  = var.encrypt_at_rest_enabled
    kms_key_id = var.kms_key_id
  }

  node_to_node_encryption {
    enabled = var.node_to_node_encryption
  }

  domain_endpoint_options {
    enforce_https       = var.enforce_https
    tls_security_policy = var.tls_security_policy
  }

  advanced_security_options {
    enabled                        = var.fine_grained_access_control_enabled
    anonymous_auth_enabled         = false
    internal_user_database_enabled = var.fine_grained_access_control_enabled

    dynamic "master_user_options" {
      for_each = var.fine_grained_access_control_enabled ? [1] : []
      content {
        master_user_name     = "admin"
        master_user_password = random_password.opensearch_master.result
      }
    }
  }

  snapshot_options {
    automated_snapshot_start_hour = var.automated_snapshot_start_hour
  }

  log_publishing_options {
    log_type                 = "INDEX_SLOW_LOGS"
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_index_slow.arn
  }

  log_publishing_options {
    log_type                 = "SEARCH_SLOW_LOGS"
    cloudwatch_log_group_arn = aws_cloudwatch_log_group.opensearch_search_slow.arn
  }

  tags = { Name = local.domain_name }

  depends_on = [aws_cloudwatch_log_resource_policy.opensearch]
}

resource "aws_cloudwatch_log_group" "opensearch_index_slow" {
  name              = "/aws/opensearch/${local.domain_name}/index-slow-logs"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_group" "opensearch_search_slow" {
  name              = "/aws/opensearch/${local.domain_name}/search-slow-logs"
  retention_in_days = 30
}

resource "aws_cloudwatch_log_resource_policy" "opensearch" {
  policy_name = "${local.name_prefix}-opensearch-log-policy"

  policy_document = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "es.amazonaws.com" }
      Action    = ["logs:PutLogEvents", "logs:CreateLogStream"]
      Resource  = "arn:aws:logs:*:${var.aws_account}:log-group:/aws/opensearch/*"
    }]
  })
}

# Access policy: allow VPC access
resource "aws_opensearch_domain_policy" "main" {
  domain_name = aws_opensearch_domain.main.domain_name

  access_policies = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { AWS = "*" }
      Action    = "es:*"
      Resource  = "${aws_opensearch_domain.main.arn}/*"
      Condition = {
        StringEquals = {
          "aws:SourceVpc" = var.vpc_id
        }
      }
    }]
  })
}
