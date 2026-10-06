# Live dashboard: agent tokens / cost / latency come from the worker's structured JSON logs
# (CloudWatch Logs Insights widgets = no custom-metric charges), plus free built-in service metrics.
locals {
  worker_lg = aws_cloudwatch_log_group.worker.name
  api_lg    = aws_cloudwatch_log_group.api.name
}

resource "aws_cloudwatch_dashboard" "agents" {
  dashboard_name = "${local.name}-agents"
  dashboard_body = jsonencode({
    widgets = [
      {
        type = "text", x = 0, y = 0, width = 24, height = 2,
        properties = { markdown = "# PhyTro - agent operations\nLabel Scout → Toxicology Analyst → Shopper Advocate on `${var.model_id}`. Cost = tokens × on-demand price (estimate)." }
      },
      {
        type = "log", x = 0, y = 2, width = 12, height = 6,
        properties = {
          title  = "Per-agent usage & estimated cost"
          region = local.region
          view   = "table"
          query  = "SOURCE '${local.worker_lg}' | filter metric = 'agent_call' | stats count(*) as calls, sum(tokens_in) as tokens_in, sum(tokens_out) as tokens_out, avg(latency_s) as avg_latency_s, avg(turns) as avg_tool_turns, sum(cost_usd) as cost_usd by agent"
        }
      },
      {
        type = "log", x = 12, y = 2, width = 12, height = 6,
        properties = {
          title  = "Estimated Bedrock cost per hour (USD)"
          region = local.region
          view   = "timeSeries"
          query  = "SOURCE '${local.worker_lg}' | filter metric = 'agent_call' | stats sum(cost_usd) as cost_usd by bin(1h)"
        }
      },
      {
        type = "log", x = 0, y = 8, width = 8, height = 6,
        properties = {
          title  = "Analysis jobs by outcome"
          region = local.region
          view   = "pie"
          query  = "SOURCE '${local.worker_lg}' | filter metric = 'job' | stats count(*) as jobs by status"
        }
      },
      {
        type = "log", x = 8, y = 8, width = 16, height = 6,
        properties = {
          title  = "Latest errors (API + worker)"
          region = local.region
          view   = "table"
          query  = "SOURCE '${local.api_lg}' | SOURCE '${local.worker_lg}' | filter level = 'error' or status = 'error' | fields @timestamp, route, error | sort @timestamp desc | limit 20"
        }
      },
      {
        type = "metric", x = 0, y = 14, width = 12, height = 6,
        properties = {
          title  = "Lambda invocations / errors"
          region = local.region
          stat   = "Sum"
          period = 300
          metrics = [
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.api.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.api.function_name],
            ["AWS/Lambda", "Invocations", "FunctionName", aws_lambda_function.worker.function_name],
            ["AWS/Lambda", "Errors", "FunctionName", aws_lambda_function.worker.function_name],
          ]
        }
      },
      {
        type = "metric", x = 12, y = 14, width = 12, height = 6,
        properties = {
          title  = "Worker duration (p50 / p90 ms) and API 4xx/5xx"
          region = local.region
          period = 300
          metrics = [
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.worker.function_name, { stat = "p50" }],
            ["AWS/Lambda", "Duration", "FunctionName", aws_lambda_function.worker.function_name, { stat = "p90" }],
            ["AWS/ApiGateway", "4xx", "ApiId", aws_apigatewayv2_api.http.id, { stat = "Sum", yAxis = "right" }],
            ["AWS/ApiGateway", "5xx", "ApiId", aws_apigatewayv2_api.http.id, { stat = "Sum", yAxis = "right" }],
          ]
        }
      },
    ]
  })
}

# Optional email alert when the agent worker fails
resource "aws_sns_topic" "alerts" {
  count = var.alert_email == "" ? 0 : 1
  name  = "${local.name}-alerts"
}

resource "aws_sns_topic_subscription" "email" {
  count     = var.alert_email == "" ? 0 : 1
  topic_arn = aws_sns_topic.alerts[0].arn
  protocol  = "email"
  endpoint  = var.alert_email
}

resource "aws_cloudwatch_metric_alarm" "worker_errors" {
  count               = var.alert_email == "" ? 0 : 1
  alarm_name          = "${local.name}-worker-errors"
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.worker.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  alarm_actions       = [aws_sns_topic.alerts[0].arn]
  treat_missing_data  = "notBreaching"
}
