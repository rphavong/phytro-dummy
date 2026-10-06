output "app_url" {
  description = "Open this in your browser"
  value       = "https://${aws_cloudfront_distribution.web.domain_name}"
}

output "api_url" {
  value = aws_apigatewayv2_api.http.api_endpoint
}

output "web_bucket" {
  value = aws_s3_bucket.web.id
}

output "cloudfront_id" {
  value = aws_cloudfront_distribution.web.id
}

output "table_name" {
  value = aws_dynamodb_table.main.name
}

output "user_pool_id" {
  value = aws_cognito_user_pool.users.id
}

output "user_pool_client_id" {
  value = aws_cognito_user_pool_client.web.id
}

output "dashboard_url" {
  value = "https://${local.region}.console.aws.amazon.com/cloudwatch/home?region=${local.region}#dashboards/dashboard/${aws_cloudwatch_dashboard.agents.dashboard_name}"
}

output "guardrail_id" {
  value = var.enable_guardrail ? aws_bedrock_guardrail.safety[0].guardrail_id : "disabled"
}
