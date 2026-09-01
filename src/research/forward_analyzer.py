import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from research.ranking import RankedNewsArticle

load_dotenv()

MODEL = "gpt-5.6-luna"

INPUT_COST_PER_MILLION = 0.20
OUTPUT_COST_PER_MILLION = 1.20


class ForwardAnalyzerError(Exception):
    """Raised when forward-looking research cannot be completed."""

    pass


@dataclass
class WatchItem:
    topic: str
    supporting_article_ids: list[int]


@dataclass
class ForwardAnalysis:
    symbol: str
    outlook: str
    confidence: str
    summary: str
    watch_items: list[WatchItem]
    supporting_article_ids: list[int]
    change_type: str
    change_summary: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float


class ForwardAnalyzer:
    """Produces an updated investment thesis from recent evidence."""

    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ForwardAnalyzerError(
                "OPENAI_API_KEY was not found in the environment."
            )

        self.client = OpenAI(api_key=api_key)

    def analyze(
        self,
        symbol: str,
        articles: list[RankedNewsArticle],
        previous_thesis: dict | None = None,
    ) -> ForwardAnalysis:
        """
        Update a company's thesis using recent evidence and prior context.

        The previous thesis provides memory so repeated evidence is not
        treated as a new development on every research run.
        """

        if not articles:
            raise ForwardAnalyzerError(
                "At least one news article is required."
            )

        article_data = []

        for article_id, ranked in enumerate(
            articles,
            start=1,
        ):
            article = ranked.article

            article_data.append(
                {
                    "id": article_id,
                    "source": article.source,
                    "published_at": (
                        article.published_at.isoformat()
                    ),
                    "headline": article.headline,
                    "summary": article.summary,
                }
            )

        previous_thesis_data = self._prepare_previous_thesis(
            previous_thesis
        )

        prompt = self._build_prompt(
            symbol=symbol,
            articles=article_data,
            previous_thesis=previous_thesis_data,
        )

        try:
            response = self.client.responses.create(
                model=MODEL,
                reasoning={"effort": "low"},
                instructions=(
                    "You maintain a forward-looking investment thesis for "
                    "a company in a short portfolio morning brief. You may "
                    "receive the previously stored thesis plus recent news. "
                    "Use the previous thesis as memory and determine what, "
                    "if anything, the recent evidence materially changes. "
                    "Do not treat information already represented in the "
                    "previous thesis as a new development merely because "
                    "it appears again in recent articles. Focus on material "
                    "developments involving earnings guidance, demand, "
                    "margins, products, customers, competition, regulation, "
                    "capital spending, financing, supply, and analyst "
                    "expectations. Use only the supplied evidence and prior "
                    "thesis. Do not add outside facts. Maintain the thesis "
                    "when new evidence does not justify changing it. "
                    "Classify the update as initial when no previous thesis "
                    "exists, unchanged when there is no meaningful new "
                    "evidence, reinforced when new evidence materially "
                    "strengthens or weakens the existing thesis without "
                    "changing its overall direction, or changed when new "
                    "evidence materially alters the thesis or outlook. "
                    "The summary represents the current thesis after "
                    "considering the new evidence. Keep it to no more than "
                    "two concise sentences covering the main support and "
                    "most important risk when both are present. "
                    "change_summary must describe what changed relative to "
                    "the prior thesis. For unchanged updates, briefly state "
                    "that no material change was identified. Provide two or "
                    "three concise watch items for the current thesis. "
                    "Select no more than three recent articles that provide "
                    "the strongest evidence for the current update. The "
                    "outlook is directional and must not predict a specific "
                    "future stock price."
                ),
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "forward_analysis",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "outlook": {
                                    "type": "string",
                                    "enum": [
                                        "bullish",
                                        "moderately bullish",
                                        "neutral",
                                        "moderately bearish",
                                        "bearish",
                                    ],
                                },
                                "confidence": {
                                    "type": "string",
                                    "enum": [
                                        "high",
                                        "medium",
                                        "low",
                                    ],
                                },
                                "summary": {
                                    "type": "string",
                                },
                                "watch_items": {
                                    "type": "array",
                                    "minItems": 2,
                                    "maxItems": 3,
                                    "items": {
                                        "type": "object",
                                        "properties": {
                                            "topic": {
                                                "type": "string",
                                            },
                                            "supporting_article_ids": {
                                                "type": "array",
                                                "items": {
                                                    "type": "integer",
                                                },
                                                "minItems": 1,
                                                "maxItems": 2,
                                            },
                                        },
                                        "required": [
                                            "topic",
                                            "supporting_article_ids",
                                        ],
                                        "additionalProperties": False,
                                    },
                                },
                                "supporting_article_ids": {
                                    "type": "array",
                                    "items": {
                                        "type": "integer",
                                    },
                                    "minItems": 1,
                                    "maxItems": 3,
                                },
                                "change_type": {
                                    "type": "string",
                                    "enum": [
                                        "initial",
                                        "unchanged",
                                        "reinforced",
                                        "changed",
                                    ],
                                },
                                "change_summary": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "outlook",
                                "confidence",
                                "summary",
                                "watch_items",
                                "supporting_article_ids",
                                "change_type",
                                "change_summary",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
            )

        except Exception as error:
            raise ForwardAnalyzerError(
                f"OpenAI request failed: {error}"
            ) from error

        try:
            result = json.loads(
                response.output_text
            )

        except (
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise ForwardAnalyzerError(
                "OpenAI returned an invalid structured response."
            ) from error

        watch_items = [
            WatchItem(
                topic=item["topic"],
                supporting_article_ids=(
                    item["supporting_article_ids"]
                ),
            )
            for item in result["watch_items"]
        ]

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        estimated_cost = (
            input_tokens
            / 1_000_000
            * INPUT_COST_PER_MILLION
            + output_tokens
            / 1_000_000
            * OUTPUT_COST_PER_MILLION
        )

        return ForwardAnalysis(
            symbol=symbol.upper(),
            outlook=result["outlook"],
            confidence=result["confidence"],
            summary=result["summary"],
            watch_items=watch_items,
            supporting_article_ids=(
                result["supporting_article_ids"]
            ),
            change_type=result["change_type"],
            change_summary=result["change_summary"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
        )

    @staticmethod
    def _prepare_previous_thesis(
        previous_thesis: dict | None,
    ) -> dict | None:
        """Keep only prior thesis fields useful for comparison."""

        if previous_thesis is None:
            return None

        return {
            "timestamp": previous_thesis.get(
                "timestamp"
            ),
            "outlook": previous_thesis.get(
                "outlook"
            ),
            "confidence": previous_thesis.get(
                "confidence"
            ),
            "summary": previous_thesis.get(
                "summary"
            ),
            "watch_items": previous_thesis.get(
                "watch_items",
                [],
            ),
            "supporting_articles": previous_thesis.get(
                "supporting_articles",
                [],
            ),
        }

    @staticmethod
    def _build_prompt(
        symbol: str,
        articles: list[dict],
        previous_thesis: dict | None,
    ) -> str:
        """Build prior context and new evidence for thesis updating."""

        if previous_thesis is None:
            previous_context = (
                "No previous thesis exists. This is the initial "
                "analysis for this company."
            )
        else:
            previous_context = json.dumps(
                previous_thesis,
                indent=2,
                default=str,
            )

        return (
            f"Update the investment thesis for "
            f"{symbol.upper()}.\n\n"
            f"Previous thesis:\n"
            f"{previous_context}\n\n"
            f"Recent candidate news articles:\n"
            f"{json.dumps(articles, indent=2)}\n\n"
            f"First determine whether the recent evidence is genuinely "
            f"new relative to the previous thesis. Then produce the "
            f"current thesis, classify the type of change, explain the "
            f"change concisely, identify the most important things to "
            f"monitor next, and select the strongest recent evidence."
        )