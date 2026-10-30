resource "aws_s3_bucket" "model" {
  bucket_prefix = "${var.project_name}-model-"
  force_destroy = var.force_destroy_model_bucket
}

resource "aws_s3_bucket_public_access_block" "model" {
  bucket                  = aws_s3_bucket.model.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_versioning" "model" {
  bucket = aws_s3_bucket.model.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "model" {
  bucket = aws_s3_bucket.model.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "model" {
  bucket = aws_s3_bucket.model.id

  rule {
    id     = "expire-old-versions"
    status = "Enabled"

    filter {}

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }

    noncurrent_version_expiration {
      noncurrent_days = 30
    }
  }
}

data "aws_iam_policy_document" "model_bucket" {
  statement {
    sid     = "DenyInsecureTransport"
    effect  = "Deny"
    actions = ["s3:*"]

    resources = [
      aws_s3_bucket.model.arn,
      "${aws_s3_bucket.model.arn}/*",
    ]

    principals {
      type        = "*"
      identifiers = ["*"]
    }

    condition {
      test     = "Bool"
      variable = "aws:SecureTransport"
      values   = ["false"]
    }
  }
}

resource "aws_s3_bucket_policy" "model" {
  bucket = aws_s3_bucket.model.id
  policy = data.aws_iam_policy_document.model_bucket.json

  depends_on = [aws_s3_bucket_public_access_block.model]
}

resource "aws_s3_object" "model" {
  bucket       = aws_s3_bucket.model.id
  key          = var.model_s3_key
  source       = local.model_artifact_path
  etag         = filemd5(local.model_artifact_path)
  content_type = "application/octet-stream"
}
