# Brokerage Agent

An automated portfolio intelligence system that analyzes my brokerage account after each trading session and delivers a personalized morning brief with portfolio performance, market context, forward-looking research, and actionable insights.

The system combines the **Charles Schwab API**, deterministic Python analytics, financial/news data, LLM-based research agents, and a serverless AWS architecture. It runs automatically every weekday morning and emails a concise report before the market opens.

## Schwab reauthorization

Schwab refresh authorizations currently expire after approximately seven days. A separate scheduled Lambda checks each evening and, when authorization is within 24 hours of expiry, emails a one-time reauthorization link. Schwab redirects to an API Gateway HTTPS callback that exchanges the code and updates Secrets Manager.

This uses API Gateway's default URL and requires no Porkbun DNS or custom domain. After deployment, run `terraform -chdir=infra output -raw schwab_callback_url` and register that exact URL in the Schwab developer portal. Deployed Lambdas receive the URL from Terraform; local login still uses `SCHWAB_CALLBACK_URL`.

## Example Morning Brief

Each report is designed to be readable in roughly 60–90 seconds.

```text
MORNING BRIEF

PORTFOLIO SNAPSHOT

Portfolio Value        $19,675.39
Daily Change               -$1.35
Portfolio Return           -0.01%
S&P 500 / VOO              -0.33%
Relative Performance       +0.33%

CHANGES

NVDA was the largest positive contributor, gaining 1.48% and
contributing approximately $55 to the portfolio.

VOO declined 0.33%, creating the largest negative contribution
because of its significant portfolio weight.

The portfolio ultimately outperformed its benchmark by 0.33%.

AGENTIC ADVICE

NVDA — Moderately Bullish | 19.2% portfolio weight

Recent developments remain supportive of the existing thesis,
although the position's portfolio weight makes future catalysts
particularly important to monitor.

Watch: upcoming company events, earnings developments, and
material changes to the existing investment thesis.
```

## How It Works

Portfolio values, returns, benchmark performance, position contributions, and transaction activity are calculated deterministically in Python. LLM agents then research relevant developments, evaluate existing investment theses, identify upcoming catalysts, and synthesize the results into a short Morning Brief.

## Architecture

```text
                    ┌──────────────────────────┐
                    │   EventBridge Scheduler  │
                    │   7:30 AM ET Weekdays    │
                    └─────────────┬────────────┘
                                  │
                                  ▼
                    ┌──────────────────────────┐
                    │        AWS Lambda        │
                    │    Morning Brief Job     │
                    └─────────────┬────────────┘
                                  │
                ┌─────────────────┴─────────────────┐
                │                                   │
                ▼                                   ▼
     ┌─────────────────────┐             ┌─────────────────────┐
     │   Secrets Manager   │             │    Charles Schwab   │
     │ API Keys + OAuth    │             │     Trader API      │
     └─────────────────────┘             └──────────┬──────────┘
                                                   │
                                                   ▼
                                      ┌─────────────────────────┐
                                      │ Deterministic Analytics │
                                      │                         │
                                      │ • Portfolio value       │
                                      │ • Daily return          │
                                      │ • Benchmark return      │
                                      │ • Contributions         │
                                      │ • Transactions          │
                                      │ • Session resolution    │
                                      └────────────┬────────────┘
                                                   │
                                                   ▼
                                      ┌─────────────────────────┐
                                      │     Research Layer      │
                                      │                         │
                                      │ • Market/news research  │
                                      │ • Movement analysis     │
                                      │ • Forward catalysts     │
                                      │ • Thesis comparison     │
                                      └────────────┬────────────┘
                                                   │
                         ┌─────────────────────────┴──────────┐
                         │                                    │
                         ▼                                    ▼
              ┌─────────────────────┐             ┌─────────────────────┐
              │      DynamoDB       │             │   Portfolio Advisor │
              │                     │             │                     │
              │ • Snapshots         │             │ Position-level      │
              │ • Investment theses │             │ reasoning and       │
              │ • Delivery state    │             │ recommendations     │
              └─────────────────────┘             └──────────┬──────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │   Editorial Agent   │
                                                  │                     │
                                                  │ Prioritize +        │
                                                  │ synthesize findings │
                                                  └──────────┬──────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │   HTML Renderer     │
                                                  └──────────┬──────────┘
                                                             │
                                                             ▼
                                                  ┌─────────────────────┐
                                                  │     Amazon SES      │
                                                  │    Morning Email    │
                                                  └─────────────────────┘
```

### Pipeline

**1. Portfolio Analytics**  
The Schwab API provides account, position, transaction, and market data. Python determines the latest completed trading session and calculates portfolio return, benchmark return, relative performance, position weights, and contributors/detractors.

**2. Research & Reasoning**  
The system researches meaningful portfolio movements and upcoming company-specific catalysts. Previous investment theses are stored in DynamoDB, allowing new information to be evaluated against prior conclusions rather than treating every run independently.

**3. Editorial Agent**  
A final LLM pass prioritizes the information and converts the larger internal analysis into two concise sections: **CHANGES**, explaining what affected the portfolio, and **AGENTIC ADVICE**, explaining what deserves attention going forward.

**4. Automated Delivery**  
The brief is rendered as responsive HTML and sent through Amazon SES. EventBridge Scheduler triggers the Lambda at **7:30 AM ET every weekday**.

## Reliability

The application stores the last successfully delivered trading session in DynamoDB.

Before performing research, each execution checks whether that session has already been delivered:

```text
New completed session?
        │
    ┌───┴───┐
   No      Yes
    │        │
  Exit    Research
             │
          Build Brief
             │
          Send Email
             │
       Record Delivery
```

This prevents duplicate emails and unnecessary API/LLM usage during retries, weekends, market holidays, or accidental repeated invocations.

## Architecture & Tech Stack

| Component | Technology |
|---|---|
| Brokerage Data | Charles Schwab Trader API |
| Application | Python |
| AI / Reasoning | OpenAI API |
| Market Research | Finnhub |
| Compute | AWS Lambda |
| Persistence | DynamoDB |
| Secrets | AWS Secrets Manager |
| Scheduling | EventBridge Scheduler |
| Email | Amazon SES |
| Observability | CloudWatch |
| Infrastructure | Terraform |

The entire production environment is defined with Terraform. Application updates follow a simple deployment workflow:

```text
Change → Test → Build Lambda → Terraform Plan → Apply
```


## Project Structure

```text
src/
└── portfolio_agent/
    ├── domain/               # Portfolio calculations and models
    ├── integrations/         # Schwab, Secrets Manager, and SES
    ├── services/             # Research and brief generation
    ├── storage/              # DynamoDB persistence
    ├── lambda_handler.py     # Morning brief entry point
    └── reauth_handler.py     # OAuth reminder and callback

infra/
├── main.tf                   # Core AWS infrastructure
└── scheduler.tf              # Automated weekday execution

scripts/
├── build_lambda.sh           # Lambda packaging
├── schwab_login.py           # Local OAuth fallback
└── check_*.py                # Connectivity checks
```

## Status

**V1 is deployed and fully automated.**

Every weekday at 7:30 AM Eastern, AWS invokes the application, identifies the latest completed market session, analyzes the portfolio, performs relevant research, generates the Morning Brief, emails it, and persists the resulting state for the next execution.

The reauthorization reminder runs daily at 6:00 PM Eastern and normally sends during the final 24 hours. It also sends a recovery link when the schedule was missed or authorization has already expired. OAuth state is stored in a TTL-enabled DynamoDB table and consumed after one callback.

For reliable delivery, use a verified address on a domain you control as `sender_email` (for example, `portfolio-agent@example.com`). In Amazon SES, verify the domain and enable Easy DKIM, then publish the DKIM CNAME records and an SPF/DMARC policy in DNS. Sending through SES with a personal iCloud address as the `From` address can be accepted by SES but still be classified as junk by iCloud because the sending-domain authentication is not aligned. SES cannot guarantee inbox placement.
