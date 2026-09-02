import os
from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key

from portfolio_agent.config import settings
from portfolio_agent.storage.serialization import (
    portfolio_to_snapshot,
    snapshot_to_portfolio,
)

DEFAULT_PORTFOLIO_ID = "main"


class DynamoDBStorageError(Exception):
    """Raised when DynamoDB portfolio storage fails."""

    pass


def running_in_lambda():
    """Return whether the application is running inside AWS Lambda."""

    return bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


def get_table():
    """
    Get the DynamoDB portfolio snapshot table.

    Local development uses the configured AWS SSO profile.
    Lambda uses credentials from its IAM execution role.
    """

    try:
        if running_in_lambda():
            dynamodb = boto3.resource(
                "dynamodb",
                region_name=settings.aws_region,
            )
        else:
            session = boto3.Session(
                profile_name=settings.aws_profile,
                region_name=settings.aws_region,
            )

            dynamodb = session.resource("dynamodb")

        return dynamodb.Table(settings.snapshots_table_name)

    except Exception as error:
        raise DynamoDBStorageError(f"Could not connect to DynamoDB: {error}") from error


def _convert_floats_to_decimal(value):
    """Recursively convert floats because DynamoDB rejects Python floats."""

    if isinstance(value, float):
        return Decimal(str(value))

    if isinstance(value, list):
        return [_convert_floats_to_decimal(item) for item in value]

    if isinstance(value, dict):
        return {key: _convert_floats_to_decimal(item) for key, item in value.items()}

    return value


def _snapshot_from_item(item):
    """
    Convert a DynamoDB item into the snapshot structure
    used by the rest of the application.
    """

    return {
        "schema_version": item["schema_version"],
        "timestamp": item["timestamp"],
        "portfolio": item["portfolio"],
    }


def save_snapshot(
    portfolio,
    portfolio_id=DEFAULT_PORTFOLIO_ID,
):
    """Save a Portfolio snapshot to DynamoDB."""

    snapshot = portfolio_to_snapshot(portfolio)

    item = {
        "portfolio_id": portfolio_id,
        **snapshot,
    }

    item = _convert_floats_to_decimal(item)

    try:
        table = get_table()

        table.put_item(Item=item)

    except Exception as error:
        raise DynamoDBStorageError(f"Could not save snapshot to DynamoDB: {error}") from error

    return snapshot["timestamp"]


def get_latest_snapshot(
    portfolio_id=DEFAULT_PORTFOLIO_ID,
):
    """Retrieve the newest DynamoDB portfolio snapshot."""

    try:
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key("portfolio_id").eq(portfolio_id),
            ScanIndexForward=False,
            Limit=1,
        )

    except Exception as error:
        raise DynamoDBStorageError(f"Could not retrieve snapshot from DynamoDB: {error}") from error

    items = response.get("Items", [])

    if not items:
        return None

    return _snapshot_from_item(items[0])


def get_latest_portfolio(
    portfolio_id=DEFAULT_PORTFOLIO_ID,
):
    """
    Retrieve the latest snapshot and reconstruct
    the Portfolio object.
    """

    snapshot = get_latest_snapshot(portfolio_id)

    if snapshot is None:
        return None

    return snapshot_to_portfolio(snapshot)


def get_snapshot_at_or_before(
    timestamp,
    portfolio_id=DEFAULT_PORTFOLIO_ID,
):
    """
    Retrieve the newest snapshot whose timestamp is
    less than or equal to the requested timestamp.
    """

    try:
        table = get_table()

        response = table.query(
            KeyConditionExpression=(
                Key("portfolio_id").eq(portfolio_id) & Key("timestamp").lte(timestamp)
            ),
            ScanIndexForward=False,
            Limit=1,
        )

    except Exception as error:
        raise DynamoDBStorageError(
            f"Could not retrieve historical snapshot from DynamoDB: {error}"
        ) from error

    items = response.get("Items", [])

    if not items:
        return None

    return _snapshot_from_item(items[0])


def get_portfolio_at_or_before(
    timestamp,
    portfolio_id=DEFAULT_PORTFOLIO_ID,
):
    """
    Retrieve the newest portfolio that existed at or
    before the requested timestamp.
    """

    snapshot = get_snapshot_at_or_before(
        timestamp=timestamp,
        portfolio_id=portfolio_id,
    )

    if snapshot is None:
        return None

    return snapshot_to_portfolio(snapshot)


def get_all_snapshots(
    portfolio_id=DEFAULT_PORTFOLIO_ID,
):
    """Retrieve all snapshots for a portfolio chronologically."""

    try:
        table = get_table()

        response = table.query(
            KeyConditionExpression=Key("portfolio_id").eq(portfolio_id),
            ScanIndexForward=True,
        )

    except Exception as error:
        raise DynamoDBStorageError(
            f"Could not retrieve snapshots from DynamoDB: {error}"
        ) from error

    snapshots = []

    for item in response.get("Items", []):
        snapshots.append(_snapshot_from_item(item))

    return snapshots
