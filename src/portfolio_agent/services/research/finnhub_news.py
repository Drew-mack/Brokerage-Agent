import html
import os
from dataclasses import dataclass
from datetime import date, datetime, timezone

import requests
FINNHUB_BASE_URL = "https://finnhub.io/api/v1"


class FinnhubError(Exception):
    """Raised when a Finnhub API request fails."""


@dataclass
class NewsArticle:
    headline: str
    summary: str
    source: str
    url: str
    published_at: datetime
    related: str
    category: str
    image_url: str | None = None


class FinnhubNewsClient:
    """Client for retrieving company-specific news from Finnhub."""

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.getenv("FINNHUB_API_KEY")

        if not self.api_key:
            raise FinnhubError(
                "FINNHUB_API_KEY was not found in the environment."
            )

        self.session = requests.Session()

    def get_company_news(
        self,
        symbol: str,
        start_date: date,
        end_date: date,
    ) -> list[NewsArticle]:
        """
        Retrieve company news for a ticker within a date range.

        Results are normalized immediately so the rest of the application
        does not depend on Finnhub's response format.
        """

        response = self.session.get(
            f"{FINNHUB_BASE_URL}/company-news",
            params={
                "symbol": symbol.upper(),
                "from": start_date.isoformat(),
                "to": end_date.isoformat(),
                "token": self.api_key,
            },
            timeout=10,
        )

        if not response.ok:
            raise FinnhubError(
                f"Finnhub request failed with status "
                f"{response.status_code}: {response.text}"
            )

        try:
            raw_articles = response.json()
        except ValueError as error:
            raise FinnhubError(
                "Finnhub returned an invalid JSON response."
            ) from error

        if not isinstance(raw_articles, list):
            raise FinnhubError(
                f"Unexpected Finnhub response: {raw_articles}"
            )

        articles = [
            self._normalize_article(article)
            for article in raw_articles
            if article.get("headline")
        ]

        articles.sort(
            key=lambda article: article.published_at,
            reverse=True,
        )

        return articles

    @staticmethod
    def _clean_text(text: str) -> str:
        """Normalize HTML entities and repair common encoding artifacts."""

        if not text:
            return ""

        text = html.unescape(text)

        try:
            text = text.encode("latin1").decode("utf-8")
        except (UnicodeEncodeError, UnicodeDecodeError):
            pass

        return text.strip()

    @staticmethod
    def _normalize_article(article: dict) -> NewsArticle:
        """Convert a Finnhub article into our internal news model."""

        timestamp = article.get("datetime", 0)

        published_at = datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )

        return NewsArticle(
            headline=FinnhubNewsClient._clean_text(
                article.get("headline", "")
            ),
            summary=FinnhubNewsClient._clean_text(
                article.get("summary", "")
            ),
            source=FinnhubNewsClient._clean_text(
                article.get("source", "")
            ),
            url=article.get("url", "").strip(),
            published_at=published_at,
            related=article.get("related", "").strip(),
            category=article.get("category", "").strip(),
            image_url=article.get("image") or None,
        )

