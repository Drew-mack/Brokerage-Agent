import json
import logging
import os

import boto3

from portfolio_agent.config import settings

logger = logging.getLogger(__name__)


def load_api_keys():
    """Load external API credentials into the process environment."""

    client = boto3.client(
        "secretsmanager",
        region_name=settings.aws_region,
    )

    response = client.get_secret_value(SecretId=(settings.api_keys_secret_name))

    secret = json.loads(response["SecretString"])

    required_keys = (
        "OPENAI_API_KEY",
        "FINNHUB_API_KEY",
    )

    for key in required_keys:
        value = secret.get(key)

        if not value:
            raise RuntimeError(f"{key} was not found in {settings.api_keys_secret_name}.")

        os.environ[key] = str(value)


def lambda_handler(
    event,
    context,
):
    """AWS Lambda entry point for the morning portfolio brief."""

    logger.info(
        "Starting portfolio morning brief",
        extra={"request_id": getattr(context, "aws_request_id", None)},
    )
    load_api_keys()

    # Import after secrets are loaded because the research clients
    # read their API credentials from environment variables.
    from portfolio_agent.services.research.research_service import (
        run_morning_brief,
    )

    result = run_morning_brief(
        send_email=True,
        write_preview=False,
        prevent_duplicate_delivery=True,
    )

    logger.info("Portfolio morning brief completed")
    return result
