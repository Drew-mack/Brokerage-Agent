resource "aws_iam_role" "portfolio_agent_scheduler" {
  name = "${local.name_prefix}-scheduler-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Effect = "Allow"

        Principal = {
          Service = "scheduler.amazonaws.com"
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

resource "aws_iam_role_policy" "portfolio_agent_scheduler" {
  name = "${local.name_prefix}-scheduler-invoke"
  role = aws_iam_role.portfolio_agent_scheduler.id

  policy = jsonencode({
    Version = "2012-10-17"

    Statement = [
      {
        Sid    = "InvokePortfolioAgent"
        Effect = "Allow"

        Action = [
          "lambda:InvokeFunction"
        ]

        Resource = aws_lambda_function.portfolio_agent.arn
      }
    ]
  })
}

resource "aws_scheduler_schedule" "portfolio_agent_morning_brief" {
  name = "${local.name_prefix}-morning-brief-weekdays"

  schedule_expression          = "cron(30 7 ? * MON-FRI *)"
  schedule_expression_timezone = "America/New_York"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.portfolio_agent.arn
    role_arn = aws_iam_role.portfolio_agent_scheduler.arn

    retry_policy {
      maximum_event_age_in_seconds = 3600
      maximum_retry_attempts       = 2
    }
  }

  state = var.environment == "staging" ? "DISABLED" : "ENABLED"

  depends_on = [
    aws_iam_role_policy.portfolio_agent_scheduler
  ]
}
