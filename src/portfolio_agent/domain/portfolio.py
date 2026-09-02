from dataclasses import dataclass, field

from portfolio_agent.integrations.schwab import SchwabClient
from portfolio_agent.integrations.schwab_auth import ReauthorizationRequired


# =========================================================
# Position Model
# =========================================================

@dataclass
class Position:
    """
    Represents one investment position in our application.

    This is OUR representation of a position, independent
    of Schwab's API response format.
    """

    symbol: str
    asset_type: str
    quantity: float
    average_price: float
    market_value: float


# =========================================================
# Account Model
# =========================================================

@dataclass
class Account:
    """
    Represents one brokerage account.
    """

    account_type: str
    total_value: float
    cash: float
    positions: list[Position] = field(default_factory=list)


# =========================================================
# Portfolio Model
# =========================================================

@dataclass
class Portfolio:
    """
    Represents the investor's complete portfolio across
    all authorized Schwab accounts.
    """

    total_value: float
    cash: float

    accounts: list[Account] = field(
        default_factory=list
    )

    positions: list[Position] = field(
        default_factory=list
    )

    # =====================================================
    # Build Portfolio From Schwab
    # =====================================================

    @classmethod
    def from_schwab(cls, raw_accounts):
        """
        Convert Schwab's raw account JSON response into our
        application's Portfolio model.
        """

        accounts = []
        all_positions = []

        portfolio_total_value = 0.0
        portfolio_cash = 0.0

        # -------------------------------------------------
        # Process each Schwab account
        # -------------------------------------------------

        for raw_account in raw_accounts:

            securities_account = raw_account.get(
                "securitiesAccount",
                {}
            )

            # ---------------------------------------------
            # Account information
            # ---------------------------------------------

            account_type = securities_account.get(
                "type",
                "UNKNOWN"
            )

            # ---------------------------------------------
            # Balances
            # ---------------------------------------------

            balances = securities_account.get(
                "currentBalances",
                {}
            )

            total_value = float(
                balances.get(
                    "liquidationValue",
                    0.0
                )
            )

            cash = float(
                balances.get(
                    "cashBalance",
                    0.0
                )
            )

            # ---------------------------------------------
            # Positions
            # ---------------------------------------------

            positions = []

            raw_positions = securities_account.get(
                "positions",
                []
            )

            for raw_position in raw_positions:

                instrument = raw_position.get(
                    "instrument",
                    {}
                )

                symbol = instrument.get(
                    "symbol",
                    "UNKNOWN"
                )

                asset_type = instrument.get(
                    "assetType",
                    "UNKNOWN"
                )

                long_quantity = float(
                    raw_position.get(
                        "longQuantity",
                        0.0
                    )
                )

                short_quantity = float(
                    raw_position.get(
                        "shortQuantity",
                        0.0
                    )
                )

                # Positive quantity = long
                # Negative quantity = short

                quantity = (
                    long_quantity
                    - short_quantity
                )

                average_price = float(
                    raw_position.get(
                        "averagePrice",
                        0.0
                    )
                )

                market_value = float(
                    raw_position.get(
                        "marketValue",
                        0.0
                    )
                )

                position = Position(
                    symbol=symbol,
                    asset_type=asset_type,
                    quantity=quantity,
                    average_price=average_price,
                    market_value=market_value,
                )

                positions.append(position)

                all_positions.append(position)

            # ---------------------------------------------
            # Create Account
            # ---------------------------------------------

            account = Account(
                account_type=account_type,
                total_value=total_value,
                cash=cash,
                positions=positions,
            )

            accounts.append(account)

            # ---------------------------------------------
            # Portfolio Totals
            # ---------------------------------------------

            portfolio_total_value += total_value
            portfolio_cash += cash

        # -------------------------------------------------
        # Create Portfolio
        # -------------------------------------------------

        return cls(
            total_value=portfolio_total_value,
            cash=portfolio_cash,
            accounts=accounts,
            positions=all_positions,
        )


# =========================================================
# Portfolio Loader
# =========================================================

def load_portfolio():
    """
    Retrieve the current portfolio from Schwab and convert
    the raw response into our Portfolio model.

    Other parts of the application will eventually be able
    to simply call:

        portfolio = load_portfolio()
    """

    client = SchwabClient()

    raw_accounts = client.get_portfolio()

    return Portfolio.from_schwab(
        raw_accounts
    )


# =========================================================
# Development Display
# =========================================================

