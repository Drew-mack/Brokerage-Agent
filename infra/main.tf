terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 6.0"
    }
  }
}

provider "aws" {
  region  = "us-east-2"
  profile = "portfolio-dev"
}

resource "aws_dynamodb_table" "portfolio_snapshots" {
  name         = "portfolio-agent-snapshots"
  billing_mode = "PAY_PER_REQUEST"

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
    Environment = "development"
  }
}

resource "aws_dynamodb_table" "portfolio_theses" {
  name         = "portfolio-agent-theses"
  billing_mode = "PAY_PER_REQUEST"

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
    Environment = "development"
  }
}

resource "aws_dynamodb_table" "portfolio_delivery_state" {
  name         = "portfolio-agent-delivery-state"
  billing_mode = "PAY_PER_REQUEST"

  hash_key = "delivery_id"

  attribute {
    name = "delivery_id"
    type = "S"
  }

  tags = {
    Project     = "Brokerage-Agent"
    Environment = "development"
  }
}

resource "aws_iam_role" "portfolio_agent_lambda" {
  name = "portfolio-agent-lambda-role"

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
    Environment = "development"
  }
}

resource "aws_iam_role_policy_attachment" "lambda_basic_execution" {
  role       = aws_iam_role.portfolio_agent_lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "portfolio_agent_permissions" {
  name = "portfolio-agent-permissions"
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
  function_name = "portfolio-agent-morning-brief"

  role    = aws_iam_role.portfolio_agent_lambda.arn
  handler = "lambda_handler.lambda_handler"

  runtime       = "python3.13"
  architectures = ["x86_64"]

  filename         = "${path.module}/../build/portfolio-agent.zip"
  source_code_hash = filebase64sha256("${path.module}/../build/portfolio-agent.zip")

  timeout     = 300
  memory_size = 512

  environment {
    variables = {
      API_KEYS_SECRET_NAME      = "portfolio-agent/api-keys"
      PORTFOLIO_SENDER_EMAIL    = "drewmack04@icloud.com"
      PORTFOLIO_RECIPIENT_EMAIL = "drewmack04@icloud.com"
    }
  }

  depends_on = [
    aws_iam_role_policy_attachment.lambda_basic_execution,
    aws_iam_role_policy.portfolio_agent_permissions
  ]

  tags = {
    Project     = "Brokerage-Agent"
    Environment = "development"
  }
}

output "lambda_function_name" {
  value = aws_lambda_function.portfolio_agent.function_name
}

output "lambda_role_arn" {
  value = aws_iam_role.portfolio_agent_lambda.arn
}