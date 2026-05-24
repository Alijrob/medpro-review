# =============================================================================
# S3 Module — medpro-review
#
# Buckets:
#   1. {project}-{env}-reports       — report output files
#   2. {project}-{env}-audit-worm    — WORM audit archive (Entry 005)
#   3. {project}-{env}-access-logs   — server access logs
#
# DECISIONS.md Entry 005: audit-worm uses S3 Object Lock in COMPLIANCE mode.
# Nothing — not even the root account — can delete these objects before
# the retention period expires. Retention = audit_retention_years years.
# =============================================================================

locals {
  name_prefix             = "${var.project}-${var.environment}"
  audit_retention_days    = var.audit_retention_years * 365
}

# ---------------------------------------------------------------------------
# Access Logs Bucket (must be created first, other buckets point to it)
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "access_logs" {
  bucket = "${local.name_prefix}-s3-access-logs"

  tags = {
    Name    = "${local.name_prefix}-s3-access-logs"
    Purpose = "s3-access-logs"
  }
}

resource "aws_s3_bucket_public_access_block" "access_logs" {
  bucket                  = aws_s3_bucket.access_logs.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "access_logs" {
  bucket = aws_s3_bucket.access_logs.id

  rule {
    id     = "expire-access-logs"
    status = "Enabled"
    expiration { days = 90 }
  }
}

# ---------------------------------------------------------------------------
# Reports Bucket
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "reports" {
  bucket = "${local.name_prefix}-reports"

  tags = {
    Name    = "${local.name_prefix}-reports"
    Purpose = "report-output"
  }
}

resource "aws_s3_bucket_versioning" "reports" {
  bucket = aws_s3_bucket.reports.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.reports_kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "reports" {
  bucket                  = aws_s3_bucket.reports.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "reports" {
  bucket        = aws_s3_bucket.reports.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "reports/"
}

resource "aws_s3_bucket_lifecycle_configuration" "reports" {
  bucket = aws_s3_bucket.reports.id

  rule {
    id     = "move-to-ia"
    status = "Enabled"

    transition {
      days          = 30
      storage_class = "STANDARD_IA"
    }

    transition {
      days          = 90
      storage_class = "GLACIER_IR"
    }

    noncurrent_version_expiration {
      noncurrent_days = 90
    }
  }
}

# Deny non-HTTPS access
resource "aws_s3_bucket_policy" "reports" {
  bucket = aws_s3_bucket.reports.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          "${aws_s3_bucket.reports.arn}",
          "${aws_s3_bucket.reports.arn}/*",
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      }
    ]
  })
}

# ---------------------------------------------------------------------------
# Audit WORM Bucket (Object Lock — COMPLIANCE mode)
# DECISIONS.md Entry 005: immutable audit archive replacing QLDB streams
# ---------------------------------------------------------------------------
resource "aws_s3_bucket" "audit_worm" {
  bucket = "${local.name_prefix}-audit-worm"

  # Object Lock MUST be enabled at bucket creation — cannot be added later
  object_lock_enabled = true

  tags = {
    Name    = "${local.name_prefix}-audit-worm"
    Purpose = "audit-worm-archive"
    Sensitivity = "CRITICAL"
  }
}

resource "aws_s3_bucket_versioning" "audit_worm" {
  bucket = aws_s3_bucket.audit_worm.id
  versioning_configuration {
    # Object Lock requires versioning; MFA delete adds extra protection
    status     = "Enabled"
    mfa_delete = "Disabled"  # Enable manually with MFA device if required
  }
}

resource "aws_s3_bucket_object_lock_configuration" "audit_worm" {
  bucket = aws_s3_bucket.audit_worm.id

  rule {
    default_retention {
      mode = "COMPLIANCE"  # COMPLIANCE: cannot be overridden even by root
      days = local.audit_retention_days
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "audit_worm" {
  bucket = aws_s3_bucket.audit_worm.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm     = "aws:kms"
      kms_master_key_id = var.audit_kms_key_arn
    }
    bucket_key_enabled = true
  }
}

resource "aws_s3_bucket_public_access_block" "audit_worm" {
  bucket                  = aws_s3_bucket.audit_worm.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_logging" "audit_worm" {
  bucket        = aws_s3_bucket.audit_worm.id
  target_bucket = aws_s3_bucket.access_logs.id
  target_prefix = "audit-worm/"
}

resource "aws_s3_bucket_policy" "audit_worm" {
  bucket = aws_s3_bucket.audit_worm.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "DenyNonHTTPS"
        Effect    = "Deny"
        Principal = "*"
        Action    = "s3:*"
        Resource = [
          "${aws_s3_bucket.audit_worm.arn}",
          "${aws_s3_bucket.audit_worm.arn}/*",
        ]
        Condition = {
          Bool = { "aws:SecureTransport" = "false" }
        }
      },
      {
        Sid       = "DenyDeleteObject"
        Effect    = "Deny"
        Principal = "*"
        Action    = ["s3:DeleteObject", "s3:DeleteObjectVersion"]
        Resource  = "${aws_s3_bucket.audit_worm.arn}/*"
      }
    ]
  })
}
