resource "aws_iam_role" "portfolio_agent_scheduler" {
  name = "portfolio-agent-scheduler-role"

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
    Environment = "development"
  }
}

resource "aws_iam_role_policy" "portfolio_agent_scheduler" {
  name = "portfolio-agent-scheduler-invoke"
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
  name = "portfolio-agent-morning-brief-weekdays"

  schedule_expression          = "cron(30 7 ? * MON-FRI *)"
  schedule_expression_timezone = "America/New_York"

  flexible_time_window {
    mode = "OFF"
  }

  target {
    arn      = aws_lambda_function.portfolio_agent.arn
    role_arn = aws_iam_role.portfolio_agent_scheduler.arn
  }

  state = "ENABLED"

  depends_on = [
    aws_iam_role_policy.portfolio_agent_scheduler
  ]
}