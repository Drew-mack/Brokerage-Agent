import json
import os

import boto3


AWS_REGION = os.getenv(
    "AWS_REGION",
    "us-east-2",
)

API_KEYS_SECRET_NAME = os.getenv(
    "API_KEYS_SECRET_NAME",
    "portfolio-agent/api-keys",
)


def load_api_keys():
    """Load external API credentials into the process environment."""

    client = boto3.client(
        "secretsmanager",
        region_name=AWS_REGION,
    )

    response = (
        client.get_secret_value(
            SecretId=(
                API_KEYS_SECRET_NAME
            )
        )
    )

    secret = json.loads(
        response["SecretString"]
    )

    required_keys = (
        "OPENAI_API_KEY",
        "FINNHUB_API_KEY",
    )

    for key in required_keys:
        value = secret.get(
            key
        )

        if not value:
            raise RuntimeError(
                f"{key} was not found in "
                f"{API_KEYS_SECRET_NAME}."
            )

        os.environ[key] = str(
            value
        )


def lambda_handler(
    event,
    context,
):
    """AWS Lambda entry point for the morning portfolio brief."""

    load_api_keys()

    # Import after secrets are loaded because the research clients
    # read their API credentials from environment variables.
    from research.research_service import (
        run_morning_brief,
    )

    result = run_morning_brief(
        send_email=True,
        write_preview=False,
        prevent_duplicate_delivery=True,
    )

    return {
        "statusCode": 200,
        "body": json.dumps(
            result
        ),
    }