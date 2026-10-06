# One zip (backend/src) serves both functions - pure Python, no third-party packages.
data "archive_file" "backend" {
  type        = "zip"
  source_dir  = "${path.module}/../backend/src"
  output_path = "${path.module}/build/backend.zip"
  excludes    = ["**/__pycache__/**", "**/*.pyc"]
}

locals {
  common_env = {
    TABLE_NAME        = aws_dynamodb_table.main.name
    MODEL_ID          = var.model_id
    GUARDRAIL_ID      = var.enable_guardrail ? aws_bedrock_guardrail.safety[0].guardrail_id : ""
    GUARDRAIL_VERSION = var.enable_guardrail ? aws_bedrock_guardrail_version.safety[0].version : ""
    OFF_USER_AGENT    = "PhyTro/1.0 (${var.off_contact})"
  }
}

resource "aws_cloudwatch_log_group" "api" {
  name              = "/aws/lambda/${local.name}-api"
  retention_in_days = var.log_retention_days
}

resource "aws_cloudwatch_log_group" "worker" {
  name              = "/aws/lambda/${local.name}-worker"
  retention_in_days = var.log_retention_days
}

resource "aws_lambda_function" "api" {
  function_name    = "${local.name}-api"
  role             = aws_iam_role.api.arn
  runtime          = "python3.12"
  handler          = "handlers.api.handler"
  filename         = data.archive_file.backend.output_path
  source_code_hash = data.archive_file.backend.output_base64sha256
  architectures    = ["arm64"] # Graviton: ~20% cheaper per GB-second
  memory_size      = 512
  timeout          = 29 # just under the API Gateway limit
  environment {
    variables = merge(local.common_env, { WORKER_FUNCTION = aws_lambda_function.worker.function_name })
  }
  depends_on = [aws_cloudwatch_log_group.api]
}

resource "aws_lambda_function" "worker" {
  function_name    = "${local.name}-worker"
  role             = aws_iam_role.worker.arn
  runtime          = "python3.12"
  handler          = "handlers.worker.handler"
  filename         = data.archive_file.backend.output_path
  source_code_hash = data.archive_file.backend.output_base64sha256
  architectures    = ["arm64"]
  memory_size      = 1024 # loads the regulatory index; more memory = faster CPU too
  timeout          = 180
  environment {
    variables = local.common_env
  }
  depends_on = [aws_cloudwatch_log_group.worker]
}

# Async invokes: don't retry a failed agent run (each retry would cost Bedrock tokens again).
resource "aws_lambda_function_event_invoke_config" "worker" {
  function_name          = aws_lambda_function.worker.function_name
  maximum_retry_attempts = 0
}
