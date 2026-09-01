import os
from datetime import datetime, timezone
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key


AWS_REGION = "us-east-2"
AWS_PROFILE = "portfolio-dev"

DYNAMODB_TABLE_NAME = "portfolio-agent-theses"


class ThesisStorageError(Exception):
    """Raised when forward-thesis storage fails."""

    pass


def running_in_lambda():
    """Return whether the application is running inside AWS Lambda."""

    return bool(
        os.getenv(
            "AWS_LAMBDA_FUNCTION_NAME"
        )
    )


def get_table():
    """
    Get the DynamoDB thesis table.

    Local development uses the configured AWS SSO profile.
    Lambda uses credentials from its IAM execution role.
    """

    try:
        if running_in_lambda():
            dynamodb = boto3.resource(
                "dynamodb",
                region_name=AWS_REGION,
            )
        else:
            session = boto3.Session(
                profile_name=AWS_PROFILE,
                region_name=AWS_REGION,
            )

            dynamodb = session.resource(
                "dynamodb"
            )

        return dynamodb.Table(
            DYNAMODB_TABLE_NAME
        )

    except Exception as error:
        raise ThesisStorageError(
            f"Could not connect to thesis table: {error}"
        ) from error


def _convert_floats_to_decimal(value):
    """Recursively convert floats because DynamoDB rejects Python floats."""

    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, list):
        return [
            _convert_floats_to_decimal(item)
            for item in value
        ]

    if isinstance(value, dict):
        return {
            key: _convert_floats_to_decimal(item)
            for key, item in value.items()
        }

    return value


def save_thesis(
    symbol: str,
    analysis,
    supporting_articles,
):
    """Persist one forward-looking company thesis."""

    timestamp = datetime.now(
        timezone.utc
    ).isoformat()

    item = {
        "symbol": symbol.upper(),
        "timestamp": timestamp,
        "outlook": analysis.outlook,
        "confidence": analysis.confidence,
        "summary": analysis.summary,
        "change_type": analysis.change_type,
        "change_summary": analysis.change_summary,
        "watch_items": [
            {
                "topic": watch_item.topic,
                "supporting_article_ids": (
                    watch_item.supporting_article_ids
                ),
            }
            for watch_item in analysis.watch_items
        ],
        "supporting_articles": [
            {
                "headline": article.headline,
                "source": article.source,
                "url": article.url,
                "published_at": (
                    article.published_at.isoformat()
                ),
            }
            for article in supporting_articles
        ],
    }

    item = _convert_floats_to_decimal(
        item
    )

    try:
        table = get_table()

        table.put_item(
            Item=item
        )

    except Exception as error:
        raise ThesisStorageError(
            f"Could not save thesis for "
            f"{symbol.upper()}: {error}"
        ) from error

    return timestamp


def get_latest_thesis(
    symbol: str,
):
    """Retrieve the most recently stored thesis for a symbol."""

    try:
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key(
                "symbol"
            ).eq(symbol.upper()),
            ScanIndexForward=False,
            Limit=1,
        )

    except Exception as error:
        raise ThesisStorageError(
            f"Could not retrieve thesis for "
            f"{symbol.upper()}: {error}"
        ) from error

    items = response.get(
        "Items",
        []
    )

    if not items:
        return None

    return items[0]


def get_thesis_history(
    symbol: str,
):
    """Retrieve stored thesis history for a symbol."""

    try:
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key(
                "symbol"
            ).eq(symbol.upper()),
            ScanIndexForward=True,
        )

    except Exception as error:
        raise ThesisStorageError(
            f"Could not retrieve thesis history for "
            f"{symbol.upper()}: {error}"
        ) from error

    return response.get(
        "Items",
        []
    )