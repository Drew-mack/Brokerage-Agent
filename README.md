# Brokerage-Agent

# Portfolio Intelligence

An automated portfolio intelligence platform that connects to the Charles Schwab API to analyze portfolio performance, explain market movements, monitor relevant events, and generate an evidence-backed Morning Brief before each trading day.

The goal is simple: **tell me how my portfolio performed, why it moved, what changed overnight, what matters today, and whether any positions require attention.**

## Example Morning Brief

### Portfolio Snapshot

**Portfolio Value:** $31,842
**Previous Session:** +$284 (+0.90%)
**S&P 500:** +0.42%
**Relative Performance:** +0.48%

### Yesterday's Drivers

**Largest Contributors**

| Position | Return | Impact |
| -------- | -----: | -----: |
| NVDA     |  +4.1% |  +$148 |
| MSFT     |  +1.2% |   +$72 |
| VTI      |  +0.6% |   +$43 |

**Largest Detractors**

| Position | Return | Impact |
| -------- | -----: | -----: |
| AMD      |  -3.2% |   -$51 |
| DIS      |  -1.4% |   -$23 |

**What happened:** Your portfolio outperformed the S&P 500 primarily due to semiconductor exposure. NVDA accounted for roughly 52% of the day's gains, while AMD partially offset performance.

### Overnight Developments

**NVDA — Export Restrictions**

New restrictions affecting AI accelerator exports were announced after market close. NVDA is trading lower in the premarket.

### Today's Market Setup

* **8:30 AM:** CPI release
* **11:00 AM:** NVDA investor conference
* **4:00 PM:** AMD earnings

### Positions Requiring Attention

**AMD — REVIEW / HOLD**

**Evidence:** AMD declined 3.2% versus a 2.6% decline in the semiconductor sector. No material company-specific filing was identified.

**Risk:** Earnings are approaching and AMD represents 11.8% of the portfolio.

**Suggested Action:** Hold and reevaluate following earnings or if portfolio concentration exceeds 12%.

**Confidence:** Moderate

### Portfolio Risk

* Technology exposure: **47%**
* Largest position: **NVDA — 14.2%**
* Cash allocation: **6.7%**
* Portfolio reporting earnings this week: **23%**

*Data current as of 7:00 AM ET.*

---

## Architecture

```text
                     Scheduled Cloud Job
                       ~7:00 AM ET
                             │
            ┌────────────────┼────────────────┐
            ▼                ▼                ▼
      Charles Schwab      Market Data     SEC / News
           API               APIs           Sources
            │                │                │
            └────────────────┼────────────────┘
                             ▼
                    Portfolio Analytics
                             │
                 ┌───────────┴───────────┐
                 ▼                       ▼
        Performance Engine        Evidence Retrieval
        • Daily returns           • SEC filings
        • Attribution             • Earnings
        • Benchmarking            • Financial news
        • Concentration           • Market events
                 │                       │
                 └───────────┬───────────┘
                             ▼
                       Agent Workflow
                  Evidence + Risk Analysis
                             │
                             ▼
                     Morning Brief
                             │
                             ▼
                           Email
```

## Core Principles

* **Deterministic calculations:** LLMs explain financial metrics but do not calculate portfolio performance.
* **Evidence-grounded analysis:** Recommendations are supported by market data, filings, earnings, and reputable news.
* **Selective recommendations:** The system can recommend taking no action rather than generating unnecessary trades.
* **Read-only brokerage access:** The platform analyzes the portfolio but does not autonomously execute trades.

## Planned Stack

**Python · FastAPI · Charles Schwab API · LangGraph · LLM API · AWS · Docker**

## Schwab API connection check

`check_schwab.py` performs the initial OAuth login if needed, refreshes a cached
token on later runs, and makes a read-only request to Schwab's account-number
endpoint. It never places an order.

1. Create an application in the [Schwab Developer Portal](https://developer.schwab.com/), and make sure its callback URL matches the value you use below exactly.
2. Export the credentials and callback URL:

   ```bash
   export SCHWAB_APP_KEY="your-app-key"
   export SCHWAB_APP_SECRET="your-app-secret"
   export SCHWAB_REDIRECT_URI="https://127.0.0.1:8182/callback"
   ```

3. Run the check:

   ```bash
   python3 check_schwab.py
   ```

   A browser window opens. Sign in, then paste the complete URL from the
   browser's address bar when it redirects to the callback. The token is saved
   to `.schwab_token.json`, which is excluded from git.

The refresh token is subject to Schwab's expiration policy. If it expires,
remove `.schwab_token.json` and run the script again to authorize.
