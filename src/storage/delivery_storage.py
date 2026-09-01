import os
from datetime import datetime, timezone

import boto3


AWS_REGION = "us-east-2"
AWS_PROFILE = "portfolio-dev"

DYNAMODB_TABLE_NAME = "portfolio-agent-delivery-state"

MORNING_BRIEF_DELIVERY_ID = "morning-brief"


class DeliveryStorageError(Exception):
    """Raised when Morning Brief delivery-state storage fails."""

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
    Get the Morning Brief delivery-state table.

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
        raise DeliveryStorageError(
            f"Could not connect to delivery-state table: {error}"
        ) from error


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
            f"Could not retrieve Morning Brief "
            f"delivery state: {error}"
        ) from error

    item = response.get(
        "Item"
    )

    if not item:
        return None

    return item.get(
        "session_date"
    )


def record_delivery(
    session_date: str,
    message_id: str,
):
    """Record a successfully delivered Morning Brief session."""

    delivered_at = datetime.now(
        timezone.utc
    ).isoformat()

    item = {
        "delivery_id": MORNING_BRIEF_DELIVERY_ID,
        "session_date": session_date,
        "message_id": message_id,
        "delivered_at": delivered_at,
    }

    try:
        table = get_table()

        table.put_item(
            Item=item
        )

    except Exception as error:
        raise DeliveryStorageError(
            f"Could not record Morning Brief "
            f"delivery state: {error}"
        ) from error