# ---------------- DynamoDB: single table, on-demand (pay per request; ~$0 at class scale) ----------------
resource "aws_dynamodb_table" "main" {
  name         = local.name
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "PK"
  range_key    = "SK"

  attribute {
    name = "PK"
    type = "S"
  }
  attribute {
    name = "SK"
    type = "S"
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  point_in_time_recovery {
    enabled = false # turn on for production; off here to save cost
  }

  server_side_encryption {
    enabled = true
  }
}

# ---------------- Cognito: sign-up / sign-in (free tier covers class usage) ----------------
resource "aws_cognito_user_pool" "users" {
  name                     = local.name
  username_attributes      = ["email"]
  auto_verified_attributes = ["email"]
  deletion_protection      = "INACTIVE"

  password_policy {
    minimum_length    = 8
    require_lowercase = true
    require_numbers   = true
    require_symbols   = false
    require_uppercase = true
  }

  account_recovery_setting {
    recovery_mechanism {
      name     = "verified_email"
      priority = 1
    }
  }

  verification_message_template {
    default_email_option = "CONFIRM_WITH_CODE"
    email_subject        = "Your PhyTro verification code"
    email_message        = "Welcome to PhyTro! Your verification code is {####}"
  }
}

resource "aws_cognito_user_pool_client" "web" {
  name                          = "${local.name}-web"
  user_pool_id                  = aws_cognito_user_pool.users.id
  generate_secret               = false # browser app: no secret
  prevent_user_existence_errors = "ENABLED"
  explicit_auth_flows           = ["ALLOW_USER_PASSWORD_AUTH", "ALLOW_REFRESH_TOKEN_AUTH", "ALLOW_USER_SRP_AUTH"]
  access_token_validity         = 1
  id_token_validity             = 1
  refresh_token_validity        = 30
  token_validity_units {
    access_token  = "hours"
    id_token      = "hours"
    refresh_token = "days"
  }
}
