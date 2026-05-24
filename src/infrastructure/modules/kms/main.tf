# =============================================================================
# KMS Module — medpro-review
#
# Creates one KMS key per data classification tier.
# Keys: aurora, elasticache, s3_reports, s3_audit, opensearch, eks_secrets
# =============================================================================

locals {
  name_prefix = "${var.project}-${var.environment}"
}

resource "aws_kms_key" "keys" {
  for_each = var.keys

  description             = each.value.description
  deletion_window_in_days = each.value.deletion_window_in_days
  enable_key_rotation     = each.value.enable_key_rotation
  multi_region            = false

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "EnableRootAccess"
        Effect = "Allow"
        Principal = {
          AWS = "arn:aws:iam::${var.aws_account}:root"
        }
        Action   = "kms:*"
        Resource = "*"
      },
      {
        Sid    = "AllowCloudWatchLogs"
        Effect = "Allow"
        Principal = {
          Service = "logs.amazonaws.com"
        }
        Action = [
          "kms:Encrypt",
          "kms:Decrypt",
          "kms:ReEncrypt*",
          "kms:GenerateDataKey*",
          "kms:DescribeKey",
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${local.name_prefix}-kms-${each.key}"
    KeyPurpose = each.key
  }
}

resource "aws_kms_alias" "keys" {
  for_each = var.keys

  name          = "alias/${local.name_prefix}-${each.key}"
  target_key_id = aws_kms_key.keys[each.key].key_id
}
