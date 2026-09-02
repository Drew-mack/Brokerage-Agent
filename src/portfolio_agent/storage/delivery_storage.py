import os
import time
from datetime import datetime, timezone

import boto3
from botocore.exceptions import ClientError

from portfolio_agent.config import settings

MORNING_BRIEF_DELIVERY_ID = "morning-brief"


class DeliveryStorageError(Exception):
    """Raised when Morning Brief delivery-state storage fails."""

    pass


class DeliveryAlreadyClaimed(DeliveryStorageError):
    """Another invocation owns the current delivery run."""


def running_in_lambda():
    """Return whether the application is running inside AWS Lambda."""

    return bool(os.getenv("AWS_LAMBDA_FUNCTION_NAME"))


def get_table():
    """
    Get the Morning Brief delivery-state table.

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

        return dynamodb.Table(settings.delivery_table_name)

    except Exception as error:
        raise DeliveryStorageError(f"Could not connect to delivery-state table: {error}") from error


def get_last_delivered_session():
    """Return the most recently delivered Morning Brief session date."""

    try:
        table = get_table()

        response = table.get_item(
            Key={
                "delivery_id": MORNING_BRIEF_DELIVERY_ID,
            }
        )

    except Exception as error:
        raise DeliveryStorageError(
            f"Could not retrieve Morning Brief delivery state: {error}"
        ) from error

    item = response.get("Item")

    if not item:
        return None

    return item.get("session_date")


def record_delivery(
    session_date: str,
    message_id: str,
):
    """Record a successfully delivered Morning Brief session."""

    delivered_at = datetime.now(timezone.utc).isoformat()

    try:
        get_table().update_item(
            Key={"delivery_id": MORNING_BRIEF_DELIVERY_ID},
            UpdateExpression=(
                "SET session_date = :session_date, message_id = :message_id, "
                "delivered_at = :delivered_at, #status = :status REMOVE expires_at"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":session_date": session_date,
                ":message_id": message_id,
                ":delivered_at": delivered_at,
                ":status": "delivered",
            },
        )

    except ClientError as error:
        raise DeliveryStorageError(
            f"Could not record Morning Brief delivery state: {error}"
        ) from error

    except Exception as error:
        raise DeliveryStorageError(
            f"Could not record Morning Brief delivery state: {error}"
        ) from error


def claim_delivery(session_date: str) -> None:
    """Atomically claim a session before performing expensive work."""

    try:
        get_table().put_item(
            Item={
                "delivery_id": MORNING_BRIEF_DELIVERY_ID,
                "session_date": session_date,
                "status": "processing",
                "claimed_at": datetime.now(timezone.utc).isoformat(),
                "expires_at": int(time.time()) + 1800,
            },
            ConditionExpression=(
                "attribute_not_exists(delivery_id) OR session_date <> :session_date "
                "OR (#status = :processing AND expires_at < :now)"
            ),
            ExpressionAttributeNames={"#status": "status"},
            ExpressionAttributeValues={
                ":session_date": session_date,
                ":processing": "processing",
                ":now": int(time.time()),
            },
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException":
            raise DeliveryAlreadyClaimed(
                f"Morning Brief for {session_date} is already claimed."
            ) from error
        raise DeliveryStorageError(f"Could not claim Morning Brief delivery: {error}") from error
