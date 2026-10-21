# Publish bucket: steward API writes golden-record JSONL here; Snowflake external stage reads it.

resource "aws_s3_bucket" "publish" {
  bucket = var.publish_bucket_name
}

resource "aws_s3_bucket_versioning" "publish" {
  bucket = aws_s3_bucket.publish.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "publish" {
  bucket = aws_s3_bucket.publish.id
  rule {
    id     = "expire-landing-files"
    status = "Enabled"
    filter {
      prefix = "golden/"
    }
    expiration {
      days = var.environment == "prod" ? 400 : 30
    }
  }
}

resource "aws_s3_bucket_notification" "publish" {
  bucket = aws_s3_bucket.publish.id

  lambda_function {
    lambda_function_arn = aws_lambda_function.publish_notifier.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "golden/"
    filter_suffix       = ".jsonl"
  }

  depends_on = [aws_lambda_permission.publish_notifier_s3]
}

# Source extracts dropped by the ERP teams, read by the Glue ingest jobs.
resource "aws_s3_bucket" "source_extracts" {
  bucket = "ledgercore-mdm-source-extracts-${var.environment}"
}

resource "aws_s3_bucket" "pipeline_artifacts" {
  bucket = "ledgercore-mdm-pipeline-artifacts-${var.environment}"
}
