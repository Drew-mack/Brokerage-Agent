from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime

from portfolio_agent.services.research.finnhub_news import NewsArticle


@dataclass
class RankedNewsArticle:
    article: NewsArticle
    score: float


LOW_VALUE_PATTERNS = (
    "most active",
    "top movers",
    "gainers and losers",
    "stocks to watch",
    "what's going on in today's session",
    "what’s going on in today's session",
    "hot stocks",
    "trending stocks",
)


PREFERRED_SOURCES = {
    "Reuters",
    "Bloomberg",
    "CNBC",
    "MarketWatch",
    "Benzinga",
}


FORWARD_LOOKING_TERMS = (
    "guidance",
    "outlook",
    "forecast",
    "expects",
    "expected",
    "demand",
    "margin",
    "margins",
    "revenue",
    "earnings",
    "product",
    "launch",
    "roadmap",
    "customer",
    "customers",
    "competition",
    "competitor",
    "regulation",
    "regulatory",
    "antitrust",
    "export",
    "restrictions",
    "investment",
    "financing",
    "capex",
    "capacity",
    "production",
    "analyst",
    "upgrade",
    "downgrade",
    "price target",
)


def rank_company_news(
    articles: list[NewsArticle],
    symbol: str,
    move_start: datetime,
    move_end: datetime,
    limit: int = 10,
    max_per_source: int = 4,
) -> list[RankedNewsArticle]:
    """
    Select a small, diverse pool of articles for movement analysis.

    The ranking removes obvious noise and favors timely, company-focused
    reporting without trying to determine what caused the stock move.
    """

    symbol = symbol.upper()

    ranked_articles = [
        RankedNewsArticle(
            article=article,
            score=_score_article(
                article=article,
                symbol=symbol,
                move_start=move_start,
                move_end=move_end,
            ),
        )
        for article in articles
    ]

    ranked_articles.sort(
        key=lambda ranked: (
            ranked.score,
            ranked.article.published_at,
        ),
        reverse=True,
    )

    return _select_diverse_articles(
        ranked_articles=ranked_articles,
        limit=limit,
        max_per_source=max_per_source,
    )


def rank_forward_news(
    articles: list[NewsArticle],
    symbol: str,
    limit: int = 12,
    max_per_source: int = 4,
) -> list[RankedNewsArticle]:
    """
    Select a diverse pool of articles containing potentially useful
    forward-looking information about a company.

    The ranking identifies promising evidence while leaving the actual
    investment interpretation to the LLM.
    """

    symbol = symbol.upper()

    ranked_articles = [
        RankedNewsArticle(
            article=article,
            score=_score_forward_article(
                article=article,
                symbol=symbol,
            ),
        )
        for article in articles
    ]

    ranked_articles.sort(
        key=lambda ranked: (
            ranked.score,
            ranked.article.published_at,
        ),
        reverse=True,
    )

    return _select_diverse_articles(
        ranked_articles=ranked_articles,
        limit=limit,
        max_per_source=max_per_source,
    )


def _select_diverse_articles(
    ranked_articles: list[RankedNewsArticle],
    limit: int,
    max_per_source: int,
) -> list[RankedNewsArticle]:
    """Preserve ranking while preventing one publisher from dominating."""

    selected = []
    source_counts = defaultdict(int)

    for ranked in ranked_articles:
        source = ranked.article.source or "Unknown"

        if source_counts[source] >= max_per_source:
            continue

        selected.append(ranked)
        source_counts[source] += 1

        if len(selected) >= limit:
            break

    return selected


def _score_article(
    article: NewsArticle,
    symbol: str,
    move_start: datetime,
    move_end: datetime,
) -> float:
    """Score an article for relevance to a historical price movement."""

    score = 0.0

    headline = article.headline.lower()
    summary = article.summary.lower()

    if any(pattern in headline for pattern in LOW_VALUE_PATTERNS):
        score -= 10

    if move_start <= article.published_at <= move_end:
        score += 3

    related_symbols = {
        related_symbol.strip().upper()
        for related_symbol in article.related.split(",")
        if related_symbol.strip()
    }

    if symbol in related_symbols:
        score += 2

    company_terms = _company_terms(symbol)

    if any(term in headline for term in company_terms):
        score += 4

    if any(term in summary for term in company_terms):
        score += 2

    if article.source in PREFERRED_SOURCES:
        score += 1

    if article.summary:
        score += 0.5

    return score


def _score_forward_article(
    article: NewsArticle,
    symbol: str,
) -> float:
    """Score an article for potential forward-looking investment value."""

    score = 0.0

    headline = article.headline.lower()
    summary = article.summary.lower()

    combined_text = f"{headline} {summary}"

    if any(pattern in headline for pattern in LOW_VALUE_PATTERNS):
        score -= 10

    related_symbols = {
        related_symbol.strip().upper()
        for related_symbol in article.related.split(",")
        if related_symbol.strip()
    }

    if symbol in related_symbols:
        score += 2

    company_terms = _company_terms(symbol)

    if any(term in headline for term in company_terms):
        score += 4

    if any(term in summary for term in company_terms):
        score += 2

    # Keyword matches only identify articles likely to contain useful
    # evidence; their contribution is capped to avoid over-ranking noise.
    matching_forward_terms = sum(1 for term in FORWARD_LOOKING_TERMS if term in combined_text)

    score += min(
        matching_forward_terms * 1.5,
        6,
    )

    if article.source in PREFERRED_SOURCES:
        score += 1

    if article.summary:
        score += 0.5

    return score


def _company_terms(
    symbol: str,
) -> tuple[str, ...]:
    """Return common company names associated with a ticker."""

    company_names = {
        "NVDA": (
            "nvda",
            "nvidia",
        ),
        "GOOG": (
            "goog",
            "google",
            "alphabet",
        ),
        "GOOGL": (
            "googl",
            "google",
            "alphabet",
        ),
        "ORCL": (
            "orcl",
            "oracle",
        ),
        "VOO": (
            "voo",
            "vanguard",
            "s&p 500",
            "s&p500",
        ),
        "SWISX": (
            "swisx",
            "schwab international",
            "international index",
        ),
    }

    return company_names.get(
        symbol.upper(),
        (symbol.lower(),),
    )
