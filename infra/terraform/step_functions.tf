# Nightly master-data pipeline: ingest both ERPs, match/merge vendors, publish to the warehouse.

resource "aws_sfn_state_machine" "nightly_mdm" {
  name     = "ledgercore-mdm-nightly-${var.environment}"
  role_arn = aws_iam_role.step_functions.arn

  definition = templatefile("${path.module}/state_machines/nightly_mdm.asl.json", {
    ingest_sap_vendors_job            = aws_glue_job.ingest_sap_vendors.name
    ingest_ebs_cost_centers_job       = aws_glue_job.ingest_ebs_cost_centers.name
    ingest_treasury_bank_accounts_job = aws_glue_job.ingest_treasury_bank_accounts.name
    match_merge_vendors_job           = aws_glue_job.match_merge_vendors.name
    publish_notifier_arn        = aws_lambda_function.publish_notifier.arn
    alert_topic_arn             = aws_sns_topic.alerts.arn
  })
}

resource "aws_cloudwatch_event_rule" "nightly" {
  name                = "ledgercore-mdm-nightly-${var.environment}"
  schedule_expression = "cron(30 6 * * ? *)" # 01:30 America/Chicago
}

resource "aws_cloudwatch_event_target" "nightly" {
  rule     = aws_cloudwatch_event_rule.nightly.name
  arn      = aws_sfn_state_machine.nightly_mdm.arn
  role_arn = aws_iam_role.events.arn
}
