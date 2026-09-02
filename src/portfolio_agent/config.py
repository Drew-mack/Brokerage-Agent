"""Runtime configuration loaded from environment variables."""

from dataclasses import dataclass
import os

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    aws_region: str = os.getenv("AWS_REGION", "us-east-2")
    aws_profile: str | None = os.getenv("AWS_PROFILE", "portfolio-dev")
    api_keys_secret_name: str = os.getenv(
        "API_KEYS_SECRET_NAME", "portfolio-agent/api-keys"
    )
    schwab_secret_name: str = os.getenv(
        "SCHWAB_SECRET_NAME", "portfolio-agent/schwab"
    )
    snapshots_table_name: str = os.getenv(
        "SNAPSHOTS_TABLE_NAME", "portfolio-agent-snapshots"
    )
    theses_table_name: str = os.getenv(
        "THESES_TABLE_NAME", "portfolio-agent-theses"
    )
    delivery_table_name: str = os.getenv(
        "DELIVERY_TABLE_NAME", "portfolio-agent-delivery-state"
    )
    sender_email: str = os.getenv("PORTFOLIO_SENDER_EMAIL", "")
    recipient_email: str = os.getenv("PORTFOLIO_RECIPIENT_EMAIL", "")
    openai_model: str = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")
    benchmark_symbol: str = os.getenv("BENCHMARK_SYMBOL", "VOO")


settings = Settings()
