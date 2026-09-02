import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

from portfolio_agent.integrations.schwab_auth import get_access_token, ReauthorizationRequired


# =========================================================
# Configuration
# =========================================================

TRADER_BASE_URL = "https://api.schwabapi.com/trader/v1"
MARKET_DATA_BASE_URL = "https://api.schwabapi.com/marketdata/v1"

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEV_DATA_DIR = PROJECT_ROOT / "dev_data"

# We'll use SPY as our initial S&P 500 benchmark.
# We can change the benchmark later without changing the
# architecture of the application.
BENCHMARK_SYMBOL = "SPY"


# =========================================================
# Exceptions
# =========================================================

class SchwabAPIError(Exception):
    """
    Raised when Schwab returns an unsuccessful API response.
    """
    pass


def iso_utc(dt: datetime) -> str:
    """Format a datetime as the UTC timestamp expected by Schwab."""

    return dt.astimezone(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# =========================================================
# Schwab Client
# =========================================================

class SchwabClient:

    def __init__(self):
        self.trader_base_url = TRADER_BASE_URL
        self.market_data_base_url = MARKET_DATA_BASE_URL

    # =====================================================
    # Internal Request Helpers
    # =====================================================

    def _get(self, base_url, endpoint, params=None):
        """
        Make an authenticated GET request to Schwab.

        Authentication and token management are handled
        entirely by auth.py.
        """

        access_token = get_access_token()

        response = requests.get(
            f"{base_url}{endpoint}",
            headers={
                "Authorization": f"Bearer {access_token}",
                "Accept": "application/json",
            },
            params=params,
            timeout=30,
        )

        if not response.ok:
            raise SchwabAPIError(
                f"Schwab API request failed.\n"
                f"Endpoint: {endpoint}\n"
                f"Status: {response.status_code}\n"
                f"Response: {response.text}"
            )

        if not response.content:
            return None

        return response.json()

    def _trader_get(self, endpoint, params=None):
        """
        GET request against Schwab's Accounts & Trading API.
        """

        return self._get(
            self.trader_base_url,
            endpoint,
            params,
        )

    def _market_get(self, endpoint, params=None):
        """
        GET request against Schwab's Market Data API.
        """

        return self._get(
            self.market_data_base_url,
            endpoint,
            params,
        )

    # =====================================================
    # Account Numbers
    # =====================================================

    def get_account_numbers(self):
        """
        Retrieve account numbers and their corresponding
        Schwab account hash values.

        Account hashes are used for account-specific requests.
        """

        return self._trader_get(
            "/accounts/accountNumbers"
        )

    # =====================================================
    # All Accounts
    # =====================================================

    def get_accounts(self, include_positions=False):
        """
        Retrieve all Schwab accounts authorized through OAuth.

        Includes balances.

        include_positions=True additionally requests current
        positions.
        """

        params = None

        if include_positions:
            params = {
                "fields": "positions"
            }

        return self._trader_get(
            "/accounts",
            params=params,
        )

    # =====================================================
    # Single Account
    # =====================================================

    def get_account(
        self,
        account_hash,
        include_positions=False,
    ):
        """
        Retrieve one specific Schwab account.

        account_hash should be the hashValue returned by
        get_account_numbers().
        """

        params = None

        if include_positions:
            params = {
                "fields": "positions"
            }

        return self._trader_get(
            f"/accounts/{account_hash}",
            params=params,
        )

    # =====================================================
    # Current Portfolio
    # =====================================================

    def get_portfolio(self):
        """
        Retrieve all accounts including balances and positions.

        Returns Schwab's raw response.
        """

        return self.get_accounts(
            include_positions=True
        )

    # =====================================================
    # Transactions
    # =====================================================

    def get_transactions(
        self,
        account_hash,
        start_date,
        end_date,
        transaction_types=None,
        symbol=None,
    ):
        """
        Retrieve transactions for an account.

        Useful for identifying:

        - trades
        - deposits
        - withdrawals
        - dividends
        - interest
        - transfers
        - other account activity

        start_date and end_date should be ISO-8601 strings.
        """

        params = {
            "startDate": start_date,
            "endDate": end_date,
        }

        if transaction_types:
            params["types"] = transaction_types

        if symbol:
            params["symbol"] = symbol

        return self._trader_get(
            f"/accounts/{account_hash}/transactions",
            params=params,
        )

    # =====================================================
    # Orders
    # =====================================================

    def get_orders(
        self,
        account_hash,
        from_entered_time,
        to_entered_time,
        max_results=100,
        status=None,
    ):
        """
        Retrieve recent orders for an account.

        Useful for detecting pending/recent trading activity.
        """

        params = {
            "fromEnteredTime": from_entered_time,
            "toEnteredTime": to_entered_time,
            "maxResults": max_results,
        }

        if status:
            params["status"] = status

        return self._trader_get(
            f"/accounts/{account_hash}/orders",
            params=params,
        )

    # =====================================================
    # Quotes
    # =====================================================

    def get_quotes(
        self,
        symbols,
        fields=None,
        indicative=False,
    ):
        """
        Retrieve current quote information for multiple symbols.

        symbols can be:

            ["AAPL", "NVDA", "MSFT"]

        or:

            "AAPL,NVDA,MSFT"
        """

        if isinstance(symbols, (list, tuple, set)):
            symbols = ",".join(symbols)

        params = {
            "symbols": symbols,
            "indicative": str(indicative).lower(),
        }

        if fields:
            params["fields"] = fields

        return self._market_get(
            "/quotes",
            params=params,
        )

    def get_quote(self, symbol, fields=None):
        """
        Retrieve quote information for one symbol.
        """

        params = None

        if fields:
            params = {
                "fields": fields
            }

        return self._market_get(
            f"/{symbol}/quotes",
            params=params,
        )

    # =====================================================
    # Price History
    # =====================================================

    def get_price_history(
        self,
        symbol,
        period_type=None,
        period=None,
        frequency_type=None,
        frequency=None,
        start_date=None,
        end_date=None,
        need_extended_hours_data=False,
        need_previous_close=True,
    ):
        """
        Retrieve historical OHLCV candles for a security.

        This will support:

        - daily return calculations
        - weekly return calculations
        - benchmark performance
        - historical security performance
        - trend calculations
        """

        params = {
            "symbol": symbol,
            "needExtendedHoursData":
                str(need_extended_hours_data).lower(),
            "needPreviousClose":
                str(need_previous_close).lower(),
        }

        if period_type is not None:
            params["periodType"] = period_type

        if period is not None:
            params["period"] = period

        if frequency_type is not None:
            params["frequencyType"] = frequency_type

        if frequency is not None:
            params["frequency"] = frequency

        if start_date is not None:
            params["startDate"] = start_date

        if end_date is not None:
            params["endDate"] = end_date

        return self._market_get(
            "/pricehistory",
            params=params,
        )

    def get_daily_price_history(
        self,
        symbol,
        period=1,
    ):
        """
        Convenience method for retrieving daily candles.

        period=1 with periodType='month' gives us enough recent
        history for initial daily/weekly analytics.
        """

        return self.get_price_history(
            symbol=symbol,
            period_type="month",
            period=period,
            frequency_type="daily",
            frequency=1,
            need_extended_hours_data=False,
            need_previous_close=True,
        )

    # =====================================================
    # Market Hours
    # =====================================================

    def get_market_hours(
        self,
        markets="equity",
        date=None,
    ):
        """
        Retrieve market-hours information.

        This can eventually help us identify weekends,
        holidays, and unusual trading schedules.
        """

        params = {
            "markets": markets,
        }

        if date:
            params["date"] = date

        return self._market_get(
            "/markets",
            params=params,
        )

    # =====================================================
    # Instrument Information
    # =====================================================

    def search_instruments(
        self,
        symbol,
        projection="symbol-search",
    ):
        """
        Search Schwab's instrument database.
        """

        return self._market_get(
            "/instruments",
            params={
                "symbol": symbol,
                "projection": projection,
            },
        )

    def get_instrument(self, cusip):
        """
        Retrieve instrument information by CUSIP.
        """

        return self._market_get(
            f"/instruments/{cusip}"
        )

    # =====================================================
    # Position Symbol Extraction
    # =====================================================

    @staticmethod
    def extract_position_symbols(accounts):
        """
        Extract unique symbols from Schwab's account response.

        This lets us automatically request market data for
        whatever securities the portfolio currently owns.
        """

        symbols = set()

        for account_wrapper in accounts:

            securities_account = account_wrapper.get(
                "securitiesAccount",
                {}
            )

            positions = securities_account.get(
                "positions",
                []
            )

            for position in positions:

                instrument = position.get(
                    "instrument",
                    {}
                )

                symbol = instrument.get("symbol")

                if symbol:
                    symbols.add(symbol)

        return sorted(symbols)

    # =====================================================
    # Market Data For Current Portfolio
    # =====================================================

    def get_portfolio_quotes(
        self,
        accounts=None,
        include_benchmark=True,
    ):
        """
        Retrieve current quotes for every security currently
        held in the portfolio.

        The benchmark is also included by default.
        """

        if accounts is None:
            accounts = self.get_portfolio()

        symbols = self.extract_position_symbols(
            accounts
        )

        if (
            include_benchmark
            and BENCHMARK_SYMBOL not in symbols
        ):
            symbols.append(BENCHMARK_SYMBOL)

        if not symbols:
            return {}

        return self.get_quotes(symbols)

    def get_portfolio_price_history(
        self,
        accounts=None,
        include_benchmark=True,
    ):
        """
        Retrieve recent daily price history for every security
        currently held plus our benchmark.

        Returns a dictionary keyed by symbol.
        """

        if accounts is None:
            accounts = self.get_portfolio()

        symbols = self.extract_position_symbols(
            accounts
        )

        if (
            include_benchmark
            and BENCHMARK_SYMBOL not in symbols
        ):
            symbols.append(BENCHMARK_SYMBOL)

        history = {}

        for symbol in symbols:

            try:

                history[symbol] = (
                    self.get_daily_price_history(
                        symbol=symbol,
                        period=1,
                    )
                )

            except SchwabAPIError as error:

                # One unusual instrument shouldn't prevent us
                # from retrieving data for every other holding.
                history[symbol] = {
                    "_error": str(error)
                }

        return history



# =========================================================

def build_development_snapshot(client):
    """
    Retrieve the major Schwab data required by our
    morning-brief application.

    This function exists for development/verification.
    Production code will call the individual methods as needed.
    """

    now = datetime.now(timezone.utc)
    seven_days_ago = now - timedelta(days=7)

    start_date = iso_utc(seven_days_ago)
    end_date = iso_utc(now)

    # =====================================================
    # Current Accounts / Positions
    # =====================================================

    accounts = client.get_portfolio()

    account_numbers = client.get_account_numbers()

    # =====================================================
    # Transactions / Orders
    # =====================================================

    account_activity = []

    for account_mapping in account_numbers:

        account_hash = (
            account_mapping["hashValue"]
        )

        try:

            transactions = (
                client.get_transactions(
                    account_hash=account_hash,
                    start_date=start_date,
                    end_date=end_date,
                )
            )

        except SchwabAPIError as error:

            transactions = {
                "_error": str(error)
            }

        try:

            orders = client.get_orders(
                account_hash=account_hash,
                from_entered_time=start_date,
                to_entered_time=end_date,
            )

        except SchwabAPIError as error:

            orders = {
                "_error": str(error)
            }

        account_activity.append({
            "account_hash": account_hash,
            "transactions": transactions,
            "orders": orders,
        })

    # =====================================================
    # Portfolio Symbols
    # =====================================================

    symbols = (
        client.extract_position_symbols(
            accounts
        )
    )

    # =====================================================
    # Quotes
    # =====================================================

    quotes = client.get_portfolio_quotes(
        accounts=accounts,
        include_benchmark=True,
    )

    # =====================================================
    # Price History
    # =====================================================

    price_history = (
        client.get_portfolio_price_history(
            accounts=accounts,
            include_benchmark=True,
        )
    )

    # =====================================================
    # Market Hours
    # =====================================================

    try:

        market_hours = (
            client.get_market_hours(
                markets="equity"
            )
        )

    except SchwabAPIError as error:

        market_hours = {
            "_error": str(error)
        }

    # =====================================================
    # Complete Snapshot
    # =====================================================

    return {
        "retrieved_at": iso_utc(now),

        "benchmark": BENCHMARK_SYMBOL,

        "portfolio_symbols": symbols,

        "accounts": accounts,

        "account_activity": account_activity,

        "market_data": {
            "quotes": quotes,
            "price_history": price_history,
            "market_hours": market_hours,
        },
    }


# =========================================================
# Local Development Test
# =========================================================
