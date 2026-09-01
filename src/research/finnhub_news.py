import html
import os
import sys
from dataclasses import dataclass
from datetime import date, datetime, timezone

import requests
from dotenv import load_dotenv


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")


load_dotenv()

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


if __name__ == "__main__":
    from ranking import rank_company_news
    from research_analyzer import ResearchAnalyzer

    client = FinnhubNewsClient()

    symbol = "NVDA"
    start_date = date(2026, 8, 27)
    end_date = date(2026, 8, 28)

    print(
        f"\nRetrieving Finnhub news for "
        f"{symbol} from {start_date} to {end_date}..."
    )

    try:
        articles = client.get_company_news(
            symbol=symbol,
            start_date=start_date,
            end_date=end_date,
        )

        print(
            f"SUCCESS: Retrieved {len(articles)} articles."
        )

        move_start = datetime(
            2026,
            8,
            27,
            20,
            0,
            tzinfo=timezone.utc,
        )

        move_end = datetime(
            2026,
            8,
            28,
            20,
            0,
            tzinfo=timezone.utc,
        )

        ranked_articles = rank_company_news(
            articles=articles,
            symbol=symbol,
            move_start=move_start,
            move_end=move_end,
            limit=10,
        )

        print()
        print("=" * 65)
        print(f"{symbol} RANKED NEWS")
        print("=" * 65)

        for index, ranked in enumerate(
            ranked_articles,
            start=1,
        ):
            article = ranked.article

            print(
                f"\n{index}. [{ranked.score:.1f}] "
                f"{article.headline}"
            )
            print(
                f"   Source:    {article.source}"
            )
            print(
                f"   Published: "
                f"{article.published_at.isoformat()}"
            )

            if article.summary:
                print(
                    f"   Summary:   {article.summary}"
                )

            print(
                f"   URL:       {article.url}"
            )

        analyzer = ResearchAnalyzer()

        analysis = analyzer.analyze_movement(
            symbol=symbol,
            return_pct=-4.57,
            articles=ranked_articles,
        )

        print()
        print("=" * 65)
        print("LLM MOVEMENT ANALYSIS")
        print("=" * 65)
        print(f"Symbol:      {analysis.symbol}")
        print(f"Confidence:  {analysis.confidence}")
        print(f"Explanation: {analysis.explanation}")
        print(
            "Sources:     "
            + ", ".join(
                str(article_id)
                for article_id in analysis.supporting_article_ids
            )
        )

        print()
        print("=" * 65)
        print("OPENAI USAGE")
        print("=" * 65)
        print(f"Input Tokens:   {analysis.input_tokens:,}")
        print(f"Output Tokens:  {analysis.output_tokens:,}")
        print(f"Estimated Cost: ${analysis.estimated_cost:.6f}")

    except FinnhubError as error:
        print(f"\nFINNHUB ERROR: {error}")