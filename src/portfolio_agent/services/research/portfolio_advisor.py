import json
import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import OpenAI

from portfolio_agent.config import settings
from portfolio_agent.services.research.forward_analyzer import ForwardAnalysis

load_dotenv()

MODEL = settings.openai_model

INPUT_COST_PER_MILLION = 0.20
OUTPUT_COST_PER_MILLION = 1.20


class PortfolioAdvisorError(Exception):
    """Raised when portfolio advice cannot be generated."""

    pass


@dataclass
class PositionAdvice:
    symbol: str
    advice: str
    input_tokens: int
    output_tokens: int
    estimated_cost: float


class PortfolioAdvisor:
    """Generates concise investment advice using portfolio context."""

    def __init__(self, api_key: str | None = None):
        api_key = api_key or os.getenv("OPENAI_API_KEY")

        if not api_key:
            raise PortfolioAdvisorError("OPENAI_API_KEY was not found in the environment.")

        self.client = OpenAI(api_key=api_key)

    def advise(
        self,
        symbol: str,
        portfolio_value: float,
        cash: float,
        positions,
        position,
        thesis: ForwardAnalysis,
        movement_explanation: str | None = None,
    ) -> PositionAdvice:
        """Generate concise advice for one portfolio position."""

        context = self._build_context(
            symbol=symbol,
            portfolio_value=portfolio_value,
            cash=cash,
            positions=positions,
            position=position,
            thesis=thesis,
            movement_explanation=movement_explanation,
        )

        try:
            response = self.client.responses.create(
                model=MODEL,
                reasoning={"effort": "medium"},
                instructions=(
                    "You are an AI portfolio advisor. Review the supplied "
                    "portfolio, position information, recent performance, "
                    "movement research when available, and forward-looking "
                    "investment research. Give your best advice about how "
                    "the investor should manage the position. "
                    "Think holistically about the position in the context "
                    "of the entire portfolio rather than evaluating it in "
                    "isolation. Consider concentration, diversification, "
                    "company outlook, evidence quality, recent developments, "
                    "risks, and changes in the investment thesis. "
                    "Distinguish short-term price movement from evidence "
                    "that materially affects the longer-term thesis. "
                    "Give specific and useful advice rather than simply "
                    "summarizing the supplied research. Focus only on what "
                    "the investor should do or consider doing and the most "
                    "important reason why. Keep the final advice to 2-3 "
                    "concise sentences suitable for a 60-90 second morning "
                    "portfolio email. Do not repeat details already covered "
                    "by the research unless necessary to justify the advice. "
                    "You may recommend increasing, maintaining, reducing, "
                    "exiting, monitoring, or otherwise managing the position "
                    "when appropriate, but do not force the advice into a "
                    "predefined category. Use only the supplied information "
                    "and do not invent facts. Do not recommend an exact "
                    "number of shares and do not execute trades."
                ),
                input=(
                    "Given the portfolio and research below, what would "
                    "you advise the investor to do with this position, "
                    "and why?\n\n"
                    f"{json.dumps(context, indent=2)}"
                ),
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "position_advice",
                        "strict": True,
                        "schema": {
                            "type": "object",
                            "properties": {
                                "advice": {
                                    "type": "string",
                                },
                            },
                            "required": [
                                "advice",
                            ],
                            "additionalProperties": False,
                        },
                    }
                },
            )

        except Exception as error:
            raise PortfolioAdvisorError(
                f"OpenAI portfolio advice request failed: {error}"
            ) from error

        try:
            result = json.loads(response.output_text)

        except (
            TypeError,
            json.JSONDecodeError,
        ) as error:
            raise PortfolioAdvisorError(
                "OpenAI returned an invalid portfolio advice response."
            ) from error

        input_tokens = response.usage.input_tokens
        output_tokens = response.usage.output_tokens

        estimated_cost = (
            input_tokens / 1_000_000 * INPUT_COST_PER_MILLION
            + output_tokens / 1_000_000 * OUTPUT_COST_PER_MILLION
        )

        return PositionAdvice(
            symbol=symbol.upper(),
            advice=result["advice"],
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost=estimated_cost,
        )

    @staticmethod
    def _build_context(
        symbol: str,
        portfolio_value: float,
        cash: float,
        positions,
        position,
        thesis: ForwardAnalysis,
        movement_explanation: str | None,
    ) -> dict:
        """Build the complete portfolio context available to the advisor."""

        portfolio_positions = []

        for portfolio_position in positions:
            portfolio_positions.append(
                {
                    "symbol": portfolio_position.symbol,
                    "portfolio_weight_pct": round(
                        portfolio_position.current_weight * 100,
                        2,
                    ),
                    "latest_return_pct": round(
                        portfolio_position.return_pct * 100,
                        2,
                    ),
                    "portfolio_contribution_pct": round(
                        portfolio_position.portfolio_contribution * 100,
                        2,
                    ),
                }
            )

        return {
            "portfolio": {
                "total_value": round(
                    portfolio_value,
                    2,
                ),
                "cash": round(
                    cash,
                    2,
                ),
                "positions": portfolio_positions,
            },
            "position_being_evaluated": {
                "symbol": symbol.upper(),
                "portfolio_weight_pct": round(
                    position.current_weight * 100,
                    2,
                ),
                "latest_return_pct": round(
                    position.return_pct * 100,
                    2,
                ),
                "portfolio_contribution_pct": round(
                    position.portfolio_contribution * 100,
                    2,
                ),
            },
            "recent_movement_research": (movement_explanation),
            "forward_research": {
                "outlook": thesis.outlook,
                "confidence": thesis.confidence,
                "summary": thesis.summary,
                "change_type": thesis.change_type,
                "change_summary": thesis.change_summary,
                "watch_items": [item.topic for item in thesis.watch_items],
            },
        }
