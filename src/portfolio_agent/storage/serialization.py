from dataclasses import asdict
from datetime import datetime, timezone

from portfolio_agent.domain.portfolio import Portfolio, Account, Position


SNAPSHOT_SCHEMA_VERSION = 1


def portfolio_to_snapshot(portfolio):
    """
    Convert a Portfolio object into our normalized
    historical snapshot format.
    """

    now = datetime.now(timezone.utc)

    return {
        "schema_version": SNAPSHOT_SCHEMA_VERSION,
        "timestamp": now.isoformat(),
        "portfolio": asdict(portfolio),
    }


def snapshot_to_portfolio(snapshot):
    """
    Convert a stored snapshot back into a Portfolio object.
    """

    try:
        portfolio_data = snapshot["portfolio"]

        accounts = []
        all_positions = []

        for account_data in portfolio_data["accounts"]:
            positions = []

            for position_data in account_data["positions"]:
                position = Position(
                    symbol=position_data["symbol"],
                    asset_type=position_data["asset_type"],
                    quantity=float(position_data["quantity"]),
                    average_price=float(
                        position_data["average_price"]
                    ),
                    market_value=float(
                        position_data["market_value"]
                    ),
                )

                positions.append(position)
                all_positions.append(position)

            account = Account(
                account_type=account_data["account_type"],
                total_value=float(
                    account_data["total_value"]
                ),
                cash=float(account_data["cash"]),
                positions=positions,
            )

            accounts.append(account)

        return Portfolio(
            total_value=float(
                portfolio_data["total_value"]
            ),
            cash=float(portfolio_data["cash"]),
            accounts=accounts,
            positions=all_positions,
        )

    except (KeyError, TypeError, ValueError) as error:
        raise ValueError(
            f"Invalid portfolio snapshot: {error}"
        ) from error


def verify_snapshot(
    original_portfolio,
    loaded_portfolio,
):
    """
    Verify that a storage round trip preserved the
    normalized Portfolio object.
    """

    if original_portfolio != loaded_portfolio:
        raise ValueError(
            "Loaded portfolio does not match "
            "the original portfolio."
        )

    return True