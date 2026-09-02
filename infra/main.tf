terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

variable "environment" {
  description = "Deployment environment name."
  type        = string
  default     = "development"
}

variable "aws_profile" {
  description = "Local AWS CLI profile used by Terraform."
  type        = string
  default     = "portfolio-dev"
}

variable "sender_email" {
  description = "Verified SES sender address."
  type        = string
  default     = "drewmack04@icloud.com"
}

variable "recipient_email" {
  description = "Email address receiving the brief."
  type        = string
  default     = "drewmack04@icloud.com"
}

locals {
  name_prefix = var.environment == "development" ? "portfolio-agent" : "portfolio-agent-${var.environment}"
  common_tags = {
    Project     = "Brokerage-Agent"
    Environment = var.environment
  }
}

provider "aws" {
  region  = "us-east-2"
  profile = var.aws_profile
}

resource "aws_dynamodb_table" "portfolio_snapshots" {
  name         = "${local.name_prefix}-snapshots"
  billing_mode = "PAY_PER_REQUEST"

  point_in_time_recovery {
    enabled = true
  }

  hash_key  = "portfolio_id"
  range_key = "timestamp"

  attribute {
    name = "portfolio_id"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Project     = "Brokerage-Agent"
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "portfolio_theses" {
  name         = "${local.name_prefix}-theses"
  billing_mode = "PAY_PER_REQUEST"

  point_in_time_recovery {
    enabled = true
  }

  hash_key  = "symbol"
  range_key = "timestamp"

  attribute {
    name = "symbol"
    type = "S"
  }

  attribute {
    name = "timestamp"
    type = "S"
  }

  tags = {
    Project     = "Brokerage-Agent"
    Environment = var.environment
  }
}

resource "aws_dynamodb_table" "portfolio_delivery_state" {
  name         = "${local.name_prefix}-delivery-state"
  billing_mode = "PAY_PER_REQUEST"

  point_in_time_recovery {
    enabled = true
  }

  ttl {
    attribute_name = "expires_at"
    enabled        = true
  }

  hash_key = "delivery_id"

  attribute {
    name = "delivery_id"
    type = "S"
  }

  tags = {
    Project     = "Brokerage-Agent"
    Environment = var.environment
  }
}

resource "aws_iam_role" "portfolio_agent_lambda" {
  name = "${local.name_prefix}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "lambda.amazonaws.com"
        }

        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Project     = "Brokerage-Agent"
    Environment = var.environment
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.portfolio_agent_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "portfolio_agent_permissions" {
  name = "${local.name_prefix}-permissions"
  role = aws_iam_role.portfolio_agent_lambda.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "PortfolioDynamoDB"
        Effect = "Allow"

        Action = [
          "dynamodb:GetItem",
          "dynamodb:PutItem",
          "dynamodb:Query",
          "dynamodb:UpdateItem"
        ]

        Resource = [
          aws_dynamodb_table.portfolio_snapshots.arn,
          aws_dynamodb_table.portfolio_theses.arn,
          aws_dynamodb_table.portfolio_delivery_state.arn
        ]
      },
      {
        Sid    = "PortfolioSecrets"
        Effect = "Allow"

        Action = [
          "secretsmanager:GetSecretValue",
          "secretsmanager:PutSecretValue"
        ]

        Resource = [
          "arn:aws:secretsmanager:us-east-2:*:secret:portfolio-agent/schwab-*",
          "arn:aws:secretsmanager:us-east-2:*:secret:portfolio-agent/api-keys-*"
        ]
      },
      {
        Sid    = "PortfolioEmail"
        Effect = "Allow"

        Action = [
          "ses:SendEmail",
          "ses:SendRawEmail"
        ]

        Resource = "*"
      }
    ]
  })
}

resource "aws_lambda_function" "portfolio_agent" {
  function_name = "${local.name_prefix}-morning-brief"

  role    = aws_iam_role.portfolio_agent_lambda.arn
  handler = "portfolio_agent.lambda_handler.lambda_handler"

  runtime       = "python3.13"
  architectures = ["x86_64"]

  filename         = "${path.module}/../build/portfolio-agent.zip"
  source_code_hash = filebase64sha256("${path.module}/../build/portfolio-agent.zip")

  timeout     = 300
  memory_size = 512

  environment {
    variables = {
      API_KEYS_SECRET_NAME      = "portfolio-agent/api-keys"
      SCHWAB_SECRET_NAME        = "portfolio-agent/schwab"
      SNAPSHOTS_TABLE_NAME      = aws_dynamodb_table.portfolio_snapshots.name
      THESES_TABLE_NAME         = aws_dynamodb_table.portfolio_theses.name
      DELIVERY_TABLE_NAME       = aws_dynamodb_table.portfolio_delivery_state.name
      PORTFOLIO_SENDER_EMAIL    = var.sender_email
      PORTFOLIO_RECIPIENT_EMAIL = var.recipient_email
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy.portfolio_agent_permissions
  ]

  tags = {
    Project     = "Brokerage-Agent"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_log_group" "portfolio_agent" {
  name              = "/aws/lambda/${aws_lambda_function.portfolio_agent.function_name}"
  retention_in_days = 30

  tags = {
    Project     = "Brokerage-Agent"
    Environment = var.environment
  }
}

resource "aws_cloudwatch_metric_alarm" "portfolio_agent_errors" {
  alarm_name          = "${local.name_prefix}-lambda-errors"
  alarm_description   = "Portfolio Agent Lambda reported an error."
  namespace           = "AWS/Lambda"
  metric_name         = "Errors"
  dimensions          = { FunctionName = aws_lambda_function.portfolio_agent.function_name }
  statistic           = "Sum"
  period              = 300
  evaluation_periods  = 1
  threshold           = 1
  comparison_operator = "GreaterThanOrEqualToThreshold"
  treat_missing_data  = "notBreaching"
}

output "lambda_function_name" {
  value = aws_lambda_function.portfolio_agent.function_name
}

output "lambda_role_arn" {
  value = aws_iam_role.portfolio_agent_lambda.arn
}
