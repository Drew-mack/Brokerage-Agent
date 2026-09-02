import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from portfolio_agent.config import settings
from portfolio_agent.services.research.ranking import RankedNewsArticle

load_dotenv()

MODEL = settings.openai_model

INPUT_COST_PER_MILLION = 0.20
OUTPUT_COST_PER_MILLION = 1.20


class ResearchAnalyzerError(Exception):
    """Raised when research analysis cannot be completed."""


@dataclass
class MovementAnalysis:
    symbol: str
    explanation: str
    confidence: str
    supporting_article_ids: list[int]
    input_tokens: int
    output_tokens: int
    estimated_cost: float


class ResearchAnalyzer:
    """Uses an LLM to analyze market research evidence."""

    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise ResearchAnalyzerError(
                "OPENAI_API_KEY was not found in the environment."
            )

        self.client = OpenAI(api_key=api_key)

    def analyze_movement(
        self,
        symbol: str,
        return_pct: float,
        articles: list[RankedNewsArticle],
    ) -> MovementAnalysis:
        """
        Select the strongest evidence and explain an observed price movement.

        The model evaluates only the supplied research and may select at most
        two articles. It should not infer a cause when the evidence is weak.
        """

        if not articles:
            raise ResearchAnalyzerError(
                "At least one news article is required."
            )

        article_data = []

        for article_id, ranked in enumerate(articles, start=1):
            article = ranked.article

            article_data.append(
                {
                    "id": article_id,
                    "source": article.source,
                    "published_at": article.published_at.isoformat(),
                    "headline": article.headline,
                    "summary": article.summary,
                }
            )

        prompt = self._build_movement_prompt(
            symbol=symbol,
            return_pct=return_pct,
            articles=article_data,
        )

        try:
            response = self.client.responses.create(
                model=MODEL,
                reasoning={
                    "effort": "low",
                },
                instructions=(
                    "You analyze financial news to explain observed security "
                    "price movements. Use only the supplied evidence. Do not "
                    "assume an article caused a price movement simply because "
                    "it mentions the company. Prefer evidence involving "
                    "earnings, guidance, company announcements, analyst "
                    "actions, regulation, macroeconomic events, or reporting "
                    "that explicitly discusses the price movement. "
                    "Select at most the 1-2 articles that provide the strongest "
                    "evidence for explaining the movement. Do not select "
                    "additional articles merely because they are relevant to "
                    "the company. If no supplied article provides adequate "
                    "evidence, select no articles and state that the cause "
                    "is unclear."
                ),
                input=prompt,
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "movement_analysis",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "explanation": {
                                    "type": "string",
                                },
                                "confidence": {
                                    "type": "string",
                                    "enum": [
                                        "high",
                                        "medium",
                                        "low",
                                    ],
                                },
                                "supporting_article_ids": {
                                    "type": "array",
                                    "items": {
                                        "type": "integer",
                                    },
                                    "minItems": 0,
                                    "maxItems": 2,
                                },
                            },
                            "required": [
                                "explanation",
                                "confidence",
                                "supporting_article_ids",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
            )
        except Exception as error:
            raise ResearchAnalyzerError(
                f"OpenAI request failed: {error}"
            ) from error

        try:
            result = json.loads(response.output_text)
        except (TypeError, json.JSONDecodeError) as error:
            raise ResearchAnalyzerError(
                "OpenAI returned an invalid structured response."
            ) from error

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        estimated_cost = (
            input_tokens / 1_000_000 * INPUT_COST_PER_MILLION
            + output_tokens / 1_000_000 * OUTPUT_COST_PER_MILLION
        )

        return MovementAnalysis(
            symbol=symbol.upper(),
            explanation=result["explanation"],
            confidence=result["confidence"],
            supporting_article_ids=result["supporting_article_ids"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
        )

    @staticmethod
    def _build_movement_prompt(
        symbol: str,
        return_pct: float,
        articles: list[dict],
    ) -> str:
        """Build the evidence provided to the movement analysis model."""

        direction = "rose" if return_pct > 0 else "fell"

        return (
            f"{symbol.upper()} {direction} {abs(return_pct):.2f}% during "
            f"the market period being analyzed.\n\n"
            f"Candidate news articles:\n"
            f"{json.dumps(articles, indent=2)}\n\n"
            f"Identify the 1-2 articles that provide the strongest evidence "
            f"for why this movement occurred. Ignore articles that are merely "
            f"related to the company but do not help explain the price move. "
            f"If none adequately explain it, select no articles. Then provide "
            f"a concise 1-2 sentence explanation suitable for a morning "
            f"portfolio brief."
        )
