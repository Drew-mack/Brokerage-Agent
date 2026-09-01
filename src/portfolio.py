from dataclasses import dataclass, field

from schwab_client import SchwabClient
from auth import ReauthorizationRequired


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

def print_portfolio(portfolio):
    """
    Pretty-print the normalized portfolio for development
    verification.
    """

    print("\n")
    print("=" * 60)
    print("PORTFOLIO")
    print("=" * 60)

    print(
        f"\nTotal Value: "
        f"${portfolio.total_value:,.2f}"
    )

    print(
        f"Cash:        "
        f"${portfolio.cash:,.2f}"
    )

    print(
        f"Accounts:    "
        f"{len(portfolio.accounts)}"
    )

    print(
        f"Positions:   "
        f"{len(portfolio.positions)}"
    )

    # =====================================================
    # Accounts
    # =====================================================

    for account_number, account in enumerate(
        portfolio.accounts,
        start=1
    ):

        print("\n")
        print("-" * 60)

        print(
            f"ACCOUNT {account_number}"
        )

        print("-" * 60)

        print(
            f"Type:        "
            f"{account.account_type}"
        )

        print(
            f"Value:       "
            f"${account.total_value:,.2f}"
        )

        print(
            f"Cash:        "
            f"${account.cash:,.2f}"
        )

        print(
            f"Positions:   "
            f"{len(account.positions)}"
        )

        # =================================================
        # Positions
        # =================================================

        for position in account.positions:

            print("\n")

            print(
                f"{position.symbol}"
            )

            print(
                f"  Asset Type:     "
                f"{position.asset_type}"
            )

            print(
                f"  Quantity:       "
                f"{position.quantity:,.4f}"
            )

            print(
                f"  Average Price:  "
                f"${position.average_price:,.2f}"
            )

            print(
                f"  Market Value:   "
                f"${position.market_value:,.2f}"
            )

    print("\n")
    print("=" * 60)
    print("END PORTFOLIO")
    print("=" * 60)
    print("\n")


# =========================================================
# Local Development Test
# =========================================================

if __name__ == "__main__":

    try:

        print(
            "\nRetrieving portfolio from Schwab..."
        )

        portfolio = load_portfolio()

        print(
            "SUCCESS: Portfolio retrieved "
            "and normalized."
        )

        print_portfolio(
            portfolio
        )

    except ReauthorizationRequired as error:

        print(
            "\nSCHWAB REAUTHORIZATION REQUIRED"
        )

        print(error)

    except Exception as error:

        print(
            "\nPORTFOLIO ERROR"
        )

        print(error)