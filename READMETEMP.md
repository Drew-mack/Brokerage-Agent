# Brokerage Agent

An automated portfolio intelligence system that analyzes my brokerage account after each trading session and delivers a personalized morning brief with portfolio performance, market context, forward-looking research, and actionable insights.

The system combines the **Charles Schwab API**, deterministic Python analytics, financial/news data, LLM-based research agents, and a serverless AWS architecture. It runs automatically every weekday morning and emails a concise report before the market opens.

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
├── analytics.py              # Portfolio calculations
├── lambda_handler.py         # AWS entry point
├── schwab_client.py          # Brokerage integration
├── brief/                    # Brief generation + HTML rendering
├── research/                 # Research and AI agents
├── storage/                  # DynamoDB persistence
├── auth_storage/             # Secrets/OAuth storage
└── mailer/                   # SES delivery

infra/
├── main.tf                   # Core AWS infrastructure
└── scheduler.tf              # Automated weekday execution

scripts/
└── build_lambda.sh           # Lambda packaging
```

## Status

**V1 is deployed and fully automated.**

Every weekday at 7:30 AM Eastern, AWS invokes the application, identifies the latest completed market session, analyzes the portfolio, performs relevant research, generates the Morning Brief, emails it, and persists the resulting state for the next execution.

Future improvements include richer portfolio risk analysis, economic/earnings calendar integration, improved OAuth reauthorization, failure alerting, and expanded historical performance analysis.