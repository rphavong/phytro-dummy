# Least privilege: each function gets only the actions it uses, scoped to exact resource ARNs.

data "aws_iam_policy_document" "lambda_trust" {
  statement {
    actions = ["sts:AssumeRole"]
    principals {
      type        = "Service"
      identifiers = ["lambda.amazonaws.com"]
    }
  }
}

# ---------- API function: read/write the table, start the worker, write its own logs ----------
resource "aws_iam_role" "api" {
  name               = "${local.name}-api-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "api" {
  statement {
    sid       = "Table"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:DeleteItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.main.arn]
  }
  statement {
    sid       = "NameSearchCatalogScan" # name search reads every stored aisle list (cached 10 min in memory)
    actions   = ["dynamodb:Scan"]
    resources = [aws_dynamodb_table.main.arn]
  }
  statement {
    sid       = "StartAgentWorker"
    actions   = ["lambda:InvokeFunction"]
    resources = [aws_lambda_function.worker.arn]
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.api.arn}:*"]
  }
}

resource "aws_iam_role_policy" "api" {
  name   = "least-privilege"
  role   = aws_iam_role.api.id
  policy = data.aws_iam_policy_document.api.json
}

# ---------- Worker function: table + ONE Bedrock model + the guardrail + logs ----------
resource "aws_iam_role" "worker" {
  name               = "${local.name}-worker-role"
  assume_role_policy = data.aws_iam_policy_document.lambda_trust.json
}

data "aws_iam_policy_document" "worker" {
  statement {
    sid       = "Table"
    actions   = ["dynamodb:GetItem", "dynamodb:PutItem", "dynamodb:UpdateItem", "dynamodb:Query"]
    resources = [aws_dynamodb_table.main.arn]
  }
  statement {
    sid     = "InvokeOnlyTheChosenModel"
    actions = ["bedrock:InvokeModel"] # the Converse API is authorized by bedrock:InvokeModel
    resources = concat(
      ["arn:aws:bedrock:*::foundation-model/${local.foundation_model_id}"],
      local.uses_profile ? ["arn:aws:bedrock:${local.region}:${local.account_id}:inference-profile/${var.model_id}"] : []
    )
  }
  dynamic "statement" {
    for_each = var.enable_guardrail ? [1] : []
    content {
      sid       = "ApplyOurGuardrail"
      actions   = ["bedrock:ApplyGuardrail"]
      resources = [aws_bedrock_guardrail.safety[0].guardrail_arn]
    }
  }
  statement {
    sid       = "Logs"
    actions   = ["logs:CreateLogStream", "logs:PutLogEvents"]
    resources = ["${aws_cloudwatch_log_group.worker.arn}:*"]
  }
}

resource "aws_iam_role_policy" "worker" {
  name   = "least-privilege"
  role   = aws_iam_role.worker.id
  policy = data.aws_iam_policy_document.worker.json
}
