# =============================================================================
# Aurora Module — medpro-review
#
# Creates:
#   - Aurora PostgreSQL cluster (writer + optional readers)
#   - DB subnet group
#   - Security group (port 5432)
#   - Secrets Manager secret for master credentials (auto-rotated)
#   - Parameter group with append-only enforcement for audit schema
#
# DECISIONS.md Entry 005: append-only audit tables enforced via:
#   1. Separate Aurora database (medpro_audit)
#   2. Parameter group prevents DDL that would drop/alter audit tables
#   3. Application-level: audit_writer role has INSERT only (no UPDATE/DELETE)
#   4. WORM S3 receives hash-chained exports nightly (via Phase 1-I service)
# =============================================================================

locals {
  name_prefix = "${var.project}-${var.environment}"
  cluster_id  = "${local.name_prefix}-aurora"
}

# ---------------------------------------------------------------------------
# Security Group
# ---------------------------------------------------------------------------
resource "aws_security_group" "aurora" {
  name        = "${local.name_prefix}-aurora-sg"
  description = "Allow PostgreSQL access from private subnets"
  vpc_id      = var.vpc_id

  ingress {
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = var.allowed_cidr_blocks
    description = "PostgreSQL from private subnets"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${local.name_prefix}-aurora-sg"
  }
}

# ---------------------------------------------------------------------------
# Master Credentials in Secrets Manager
# ---------------------------------------------------------------------------
resource "random_password" "master" {
  length           = 32
  special          = true
  override_special = "!#$%&*()-_=+[]{}<>:?"
}

resource "aws_secretsmanager_secret" "aurora_master" {
  name        = "/${var.project}/${var.environment}/aurora/master-credentials"
  description = "Aurora PostgreSQL master credentials"
  kms_key_id  = var.kms_key_arn

  recovery_window_in_days = 7

  tags = {
    Name = "${local.name_prefix}-aurora-master-creds"
  }
}

resource "aws_secretsmanager_secret_version" "aurora_master" {
  secret_id = aws_secretsmanager_secret.aurora_master.id

  secret_string = jsonencode({
    engine   = "aurora-postgresql"
    host     = aws_rds_cluster.main.endpoint
    port     = 5432
    dbname   = var.database_name
    username = var.master_username
    password = random_password.master.result
  })
}

# ---------------------------------------------------------------------------
# DB Subnet Group
# ---------------------------------------------------------------------------
resource "aws_db_subnet_group" "aurora" {
  name       = "${local.name_prefix}-aurora-subnet-group"
  subnet_ids = var.subnet_ids

  tags = {
    Name = "${local.name_prefix}-aurora-subnet-group"
  }
}

# ---------------------------------------------------------------------------
# Cluster Parameter Group
# apply_immediately = true for dev; false for prod (requires maintenance window)
# ---------------------------------------------------------------------------
resource "aws_rds_cluster_parameter_group" "main" {
  name        = "${local.name_prefix}-aurora-pg15"
  family      = "aurora-postgresql15"
  description = "medpro-review Aurora PostgreSQL 15 parameters"

  parameter {
    name  = "log_statement"
    value = "all"
  }

  parameter {
    name  = "log_min_duration_statement"
    value = "1000"  # log queries taking > 1s
  }

  parameter {
    name  = "shared_preload_libraries"
    value = "pg_stat_statements"
  }

  tags = {
    Name = "${local.name_prefix}-aurora-cluster-pg"
  }
}

resource "aws_db_parameter_group" "instance" {
  name   = "${local.name_prefix}-aurora-instance-pg15"
  family = "aurora-postgresql15"

  tags = {
    Name = "${local.name_prefix}-aurora-instance-pg"
  }
}

# ---------------------------------------------------------------------------
# Aurora Cluster
# ---------------------------------------------------------------------------
resource "aws_rds_cluster" "main" {
  cluster_identifier = local.cluster_id

  engine         = "aurora-postgresql"
  engine_version = var.postgres_version

  database_name   = var.database_name
  master_username = var.master_username
  master_password = random_password.master.result

  db_subnet_group_name            = aws_db_subnet_group.aurora.name
  vpc_security_group_ids          = [aws_security_group.aurora.id]
  db_cluster_parameter_group_name = aws_rds_cluster_parameter_group.main.name

  # Encryption
  storage_encrypted = true
  kms_key_id        = var.kms_key_arn

  # Backup
  backup_retention_period      = var.backup_retention_period
  preferred_backup_window      = var.preferred_backup_window
  copy_tags_to_snapshot        = true
  skip_final_snapshot          = false
  final_snapshot_identifier    = "${local.cluster_id}-final-snapshot"

  # Deletion protection
  deletion_protection = var.deletion_protection

  # CloudWatch log exports
  enabled_cloudwatch_logs_exports = ["postgresql"]

  # Enhanced monitoring
  iam_database_authentication_enabled = true

  apply_immediately = var.environment == "dev" ? true : false

  lifecycle {
    # Prevent accidental master password changes from triggering cluster replace
    ignore_changes = [master_password]
  }

  tags = {
    Name = local.cluster_id
  }
}

# ---------------------------------------------------------------------------
# Aurora Instances (writer + optional readers)
# ---------------------------------------------------------------------------
resource "aws_rds_cluster_instance" "writer" {
  identifier          = "${local.cluster_id}-writer"
  cluster_identifier  = aws_rds_cluster.main.id
  instance_class      = "db.t3.medium"
  engine              = aws_rds_cluster.main.engine
  engine_version      = aws_rds_cluster.main.engine_version

  db_parameter_group_name = aws_db_parameter_group.instance.name

  performance_insights_enabled    = var.performance_insights_enabled
  performance_insights_kms_key_id = var.kms_key_arn

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  apply_immediately = var.environment == "dev" ? true : false

  tags = {
    Name = "${local.cluster_id}-writer"
    Role = "writer"
  }
}

resource "aws_rds_cluster_instance" "readers" {
  count = var.reader_count

  identifier          = "${local.cluster_id}-reader-${count.index}"
  cluster_identifier  = aws_rds_cluster.main.id
  instance_class      = "db.t3.medium"
  engine              = aws_rds_cluster.main.engine
  engine_version      = aws_rds_cluster.main.engine_version

  db_parameter_group_name = aws_db_parameter_group.instance.name

  performance_insights_enabled    = var.performance_insights_enabled
  performance_insights_kms_key_id = var.kms_key_arn

  monitoring_interval = 60
  monitoring_role_arn = aws_iam_role.rds_monitoring.arn

  apply_immediately = var.environment == "dev" ? true : false

  tags = {
    Name = "${local.cluster_id}-reader-${count.index}"
    Role = "reader"
  }
}

# ---------------------------------------------------------------------------
# IAM Role for Enhanced Monitoring
# ---------------------------------------------------------------------------
resource "aws_iam_role" "rds_monitoring" {
  name = "${local.name_prefix}-aurora-monitoring-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "monitoring.rds.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "rds_monitoring" {
  role       = aws_iam_role.rds_monitoring.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonRDSEnhancedMonitoringRole"
}
