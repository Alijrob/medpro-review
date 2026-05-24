# =============================================================================
# IAM Module — medpro-review
#
# Creates:
#   - IRSA roles for each application namespace
#   - Audit writer role (INSERT-only access to Aurora audit DB + WORM S3)
#   - Secrets Manager read role (for app pods)
#   - Base IAM policies reused across services
# =============================================================================

locals {
  name_prefix   = "${var.project}-${var.environment}"
  oidc_provider = replace(var.oidc_issuer_url, "https://", "")
}

# ---------------------------------------------------------------------------
# IRSA Trust Policy Factory (reused per namespace/service-account)
# ---------------------------------------------------------------------------
data "aws_iam_policy_document" "irsa_trust" {
  for_each = toset(var.app_namespaces)

  statement {
    actions = ["sts:AssumeRoleWithWebIdentity"]
    effect  = "Allow"

    principals {
      type        = "Federated"
      identifiers = [var.oidc_provider_arn]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:sub"
      values   = ["system:serviceaccount:${each.value}:${each.value}-sa"]
    }

    condition {
      test     = "StringEquals"
      variable = "${local.oidc_provider}:aud"
      values   = ["sts.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app_roles" {
  for_each = toset(var.app_namespaces)

  name               = "${local.name_prefix}-irsa-${each.value}"
  assume_role_policy = data.aws_iam_policy_document.irsa_trust[each.value].json

  tags = {
    Name      = "${local.name_prefix}-irsa-${each.value}"
    Namespace = each.value
  }
}

# ---------------------------------------------------------------------------
# Secrets Manager Read Policy (all app pods can read their own secrets)
# ---------------------------------------------------------------------------
resource "aws_iam_policy" "secrets_read" {
  name        = "${local.name_prefix}-secrets-read"
  description = "Allow reading Secrets Manager secrets for medpro-review"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ReadSecrets"
      Effect = "Allow"
      Action = [
        "secretsmanager:GetSecretValue",
        "secretsmanager:DescribeSecret",
      ]
      Resource = "arn:aws:secretsmanager:*:${var.aws_account}:secret:/${var.project}/*"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "app_secrets_read" {
  for_each   = toset(var.app_namespaces)
  role       = aws_iam_role.app_roles[each.value].name
  policy_arn = aws_iam_policy.secrets_read.arn
}

# ---------------------------------------------------------------------------
# Audit Writer Policy (S3 WORM write only — no read, no delete)
# Used by the audit-writer service (C5-audit / Phase 1-I)
# ---------------------------------------------------------------------------
resource "aws_iam_policy" "audit_writer" {
  name        = "${local.name_prefix}-audit-writer"
  description = "Allow writing to WORM audit S3 bucket only"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid    = "AuditWORMWrite"
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:PutObjectRetention",
          "s3:PutObjectLegalHold",
        ]
        Resource = "${var.audit_worm_bucket_arn}/*"
      },
      {
        Sid    = "AuditWORMListBucket"
        Effect = "Allow"
        Action = "s3:ListBucket"
        Resource = var.audit_worm_bucket_arn
      },
      {
        Sid    = "DenyAuditDelete"
        Effect = "Deny"
        Action = [
          "s3:DeleteObject",
          "s3:DeleteObjectVersion",
          "s3:AbortMultipartUpload",
        ]
        Resource = "${var.audit_worm_bucket_arn}/*"
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Reports Read/Write Policy
# ---------------------------------------------------------------------------
resource "aws_iam_policy" "reports_rw" {
  name        = "${local.name_prefix}-reports-rw"
  description = "Allow reading and writing report files"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid    = "ReportsReadWrite"
      Effect = "Allow"
      Action = [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "s3:ListBucket",
      ]
      Resource = [
        var.reports_bucket_arn,
        "${var.reports_bucket_arn}/*",
      ]
    }]
  })
}

resource "aws_iam_role_policy_attachment" "reports_rw" {
  role       = aws_iam_role.app_roles["reports"].name
  policy_arn = aws_iam_policy.reports_rw.arn
}
