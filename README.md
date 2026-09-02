# Portfolio Agent

Portfolio Agent is a read-only portfolio intelligence service. It retrieves a personal portfolio from Charles Schwab, calculates deterministic performance analytics, gathers market news, uses OpenAI models to explain movements and evaluate thesis changes, renders a morning brief, and delivers it through Amazon SES.

## Runtime architecture

```text
EventBridge Scheduler (7:30 AM ET, weekdays)
                    |
                    v
AWS Lambda: portfolio_agent.lambda_handler.lambda_handler
                    |
       +------------+-------------+
       |                          |
       v                          v
Schwab + market data       DynamoDB snapshots
       |                          |
       +------------+-------------+
                    v
       Deterministic analytics
                    |
       Finnhub + OpenAI research
                    |
       HTML brief + Amazon SES
                    |
       DynamoDB delivery state
```

The system does not place trades. Portfolio calculations remain deterministic; models receive verified facts and produce explanations, thesis analysis, and concise considerations.

## Repository layout

```text
src/portfolio_agent/
  lambda_handler.py       AWS entry point
  config.py               environment-backed settings
  domain/                 portfolio, transactions, analytics
  integrations/           Schwab, OAuth, Finnhub, SES, OpenAI boundaries
  services/               research and brief orchestration
  storage/                DynamoDB and local serialization adapters
scripts/                  local utilities and Lambda packaging
tests/                    unit tests with no external API calls
infra/                    Terraform resources
```

## Local development

Use Python 3.13 and install development dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Set local-only values in `.env` or the shell. Never commit `.env`, OAuth tokens, portfolio snapshots, or raw Schwab responses.

Required values include:

```text
SCHWAB_CLIENT_ID=...
SCHWAB_CLIENT_SECRET=...
SCHWAB_CALLBACK_URL=https://127.0.0.1:8182/callback
OPENAI_API_KEY=...
FINNHUB_API_KEY=...
AWS_PROFILE=portfolio-dev
AWS_REGION=us-east-2
```

Initial Schwab authorization is interactive and should be performed locally:

```bash
PYTHONPATH=src python scripts/schwab_login.py
PYTHONPATH=src python scripts/check_schwab.py
```

The resulting OAuth state is stored in `tokens.json` locally or in the `portfolio-agent/schwab` Secrets Manager secret in Lambda. Lambda refreshes the token without opening a browser.

## Tests and quality checks

```bash
pytest
ruff check src tests scripts
python -m compileall -q src
```

## Lambda deployment

Build the deployment package from the repository root:

```bash
./scripts/build_lambda.sh
```

The package handler is `portfolio_agent.lambda_handler.lambda_handler`. Terraform expects the generated archive at `build/portfolio-agent.zip`.

Apply infrastructure from `infra/` using the intended AWS credentials and a configured remote Terraform backend before using a shared or production environment:

```bash
terraform init
terraform plan
terraform apply
```

The current Terraform configuration is a development deployment in `us-east-2`. Before production use, provide separate state, names, email identities, and credentials for each environment.

## Operational notes

- DynamoDB stores portfolio snapshots, thesis history, and delivery state.
- A portfolio snapshot is saved on every successful analytics run and is used as the next historical baseline.
- Delivery state is claimed atomically to prevent concurrent Lambda invocations from sending duplicate briefs.
- Secrets are loaded from Secrets Manager at invocation time; credentials and raw financial data are not logged.
- CloudWatch logs are retained for 30 days by the supplied Terraform configuration.
