# Publish notifier: fires on every golden-record file and calls the Snowflake load procedure.

data "archive_file" "publish_notifier" {
  type        = "zip"
  source_file = "${path.module}/lambda/publish_notifier.py"
  output_path = "${path.module}/.build/publish_notifier.zip"
}

resource "aws_lambda_function" "publish_notifier" {
  function_name    = "ledgercore-mdm-publish-notifier-${var.environment}"
  role             = aws_iam_role.publish_notifier.arn
  handler          = "publish_notifier.handler"
  runtime          = "python3.12"
  timeout          = 60
  filename         = data.archive_file.publish_notifier.output_path
  source_code_hash = data.archive_file.publish_notifier.output_base64sha256

  environment {
    variables = {
      MDM_ENV                = var.environment
      SNOWFLAKE_ACCOUNT_URL  = var.snowflake_account_url
      SNOWFLAKE_SECRET_ARN   = aws_secretsmanager_secret.snowflake.arn
      COST_CENTER_CODE_WIDTH = tostring(var.cost_center_code_width)
      ALERT_TOPIC_ARN        = aws_sns_topic.alerts.arn
    }
  }
}

resource "aws_lambda_permission" "publish_notifier_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.publish_notifier.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.publish.arn
}

resource "aws_secretsmanager_secret" "snowflake" {
  name = "ledgercore/mdm/${var.environment}/snowflake-loader"
}

resource "aws_sns_topic" "alerts" {
  name = "ledgercore-mdm-alerts-${var.environment}"
}

resource "aws_sns_topic_subscription" "alerts_email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
