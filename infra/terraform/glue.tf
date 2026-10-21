# PySpark ingest and match/merge jobs (pipelines/jobs) run on Glue 4.0.

resource "aws_security_group" "glue" {
  name   = "ledgercore-mdm-glue-${var.environment}"
  vpc_id = var.vpc_id
}

locals {
  glue_default_args = {
    "--job-language"                     = "python"
    "--enable-metrics"                   = "true"
    "--enable-continuous-cloudwatch-log" = "true"
    "--extra-py-files"                   = "s3://${aws_s3_bucket.pipeline_artifacts.bucket}/wheels/ledgercore_mdm-4.7.2-py3-none-any.whl"
    "--MDM_ENV"                          = var.environment
    "--MDM_WAREHOUSE"                    = "snowflake"
    "--SOURCE_BUCKET"                    = aws_s3_bucket.source_extracts.bucket
    "--COST_CENTER_CODE_WIDTH"           = tostring(var.cost_center_code_width)
  }
}

resource "aws_glue_job" "ingest_sap_vendors" {
  name              = "ledgercore-mdm-ingest-sap-vendors-${var.environment}"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = var.glue_worker_count

  command {
    script_location = "s3://${aws_s3_bucket.pipeline_artifacts.bucket}/jobs/pipelines/jobs/ingest_sap_vendors.py"
    python_version  = "3"
  }
  default_arguments = local.glue_default_args
}

resource "aws_glue_job" "ingest_ebs_cost_centers" {
  name              = "ledgercore-mdm-ingest-ebs-cost-centers-${var.environment}"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "4.0"
  worker_type       = "G.1X"
  number_of_workers = var.glue_worker_count

  command {
    script_location = "s3://${aws_s3_bucket.pipeline_artifacts.bucket}/jobs/pipelines/jobs/ingest_ebs_cost_centers.py"
    python_version  = "3"
  }
  default_arguments = local.glue_default_args
}

resource "aws_glue_job" "match_merge_vendors" {
  name              = "ledgercore-mdm-match-merge-vendors-${var.environment}"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "4.0"
  worker_type       = "G.2X"
  number_of_workers = var.glue_worker_count

  command {
    script_location = "s3://${aws_s3_bucket.pipeline_artifacts.bucket}/jobs/pipelines/jobs/match_merge_vendors.py"
    python_version  = "3"
  }
  default_arguments = local.glue_default_args
}

# Legacy v1 loader kept alive for the APAC entities that still send fixed-width extracts.
# Scheduled weekly; see legacy/mdm_batch_v1/README.md.
resource "aws_glue_job" "legacy_cc_loader" {
  name              = "ledgercore-mdm-legacy-cc-loader-${var.environment}"
  role_arn          = aws_iam_role.glue.arn
  glue_version      = "2.0"
  worker_type       = "Standard"
  number_of_workers = 2

  command {
    script_location = "s3://${aws_s3_bucket.pipeline_artifacts.bucket}/jobs/legacy/mdm_batch_v1/cc_loader.py"
    python_version  = "3"
  }
  default_arguments = merge(local.glue_default_args, {
    "--extra-py-files" = "s3://${aws_s3_bucket.pipeline_artifacts.bucket}/jobs/legacy/mdm_batch_v1/vendor_dedupe.py"
  })
}

resource "aws_glue_trigger" "legacy_weekly" {
  name     = "ledgercore-mdm-legacy-cc-weekly-${var.environment}"
  type     = "SCHEDULED"
  schedule = "cron(0 3 ? * SUN *)"
  enabled  = var.environment == "prod"

  actions {
    job_name = aws_glue_job.legacy_cc_loader.name
  }
}
