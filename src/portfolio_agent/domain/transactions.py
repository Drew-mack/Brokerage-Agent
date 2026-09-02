from dataclasses import dataclass, field

from portfolio_agent.integrations.schwab import SchwabClient, iso_utc

# =========================================================
# Transaction Categories
# =========================================================

TRADE = "TRADE"
DEPOSIT = "DEPOSIT"
WITHDRAWAL = "WITHDRAWAL"
INCOME = "INCOME"
TRANSFER = "TRANSFER"
OTHER = "OTHER"


# =========================================================
# Data Models
# =========================================================


@dataclass
class Transaction:
    activity_id: int | None
    time: str
    category: str
    schwab_type: str
    description: str
    net_amount: float

    symbol: str | None = None
    quantity: float | None = None
    price: float | None = None


@dataclass
class TransactionSummary:
    start_time: str
    end_time: str

    transactions: list[Transaction] = field(default_factory=list)

    trades: list[Transaction] = field(default_factory=list)

    transfers: list[Transaction] = field(default_factory=list)

    income: list[Transaction] = field(default_factory=list)

    other: list[Transaction] = field(default_factory=list)

    deposits: float = 0.0
    withdrawals: float = 0.0
    dividends_and_interest: float = 0.0

    @property
    def net_external_cash_flow(self):
        return self.deposits - self.withdrawals


# =========================================================
# Classification
# =========================================================


def classify_transaction(raw_transaction):
    """
    Translate Schwab's transaction types into the small set
    of categories needed by the portfolio application.

    We intentionally keep this conservative. Anything we
    cannot confidently classify becomes OTHER.
    """

    schwab_type = raw_transaction.get("type", "")

    description = raw_transaction.get("description", "")

    description_lower = description.lower()

    # -----------------------------------------------------
    # Security transfers
    # -----------------------------------------------------

    # Schwab may report transferred securities as TRADE.
    # We observed this with "System transfer" transactions.

    if schwab_type == "RECEIVE_AND_DELIVER" or "system transfer" in description_lower:
        return TRANSFER

    # -----------------------------------------------------
    # Trades
    # -----------------------------------------------------

    if schwab_type == "TRADE":
        return TRADE

    # -----------------------------------------------------
    # Investment income
    # -----------------------------------------------------

    if schwab_type == "DIVIDEND_OR_INTEREST":
        return INCOME

    # -----------------------------------------------------
    # External cash coming into the portfolio
    # -----------------------------------------------------

    if schwab_type in {
        "ACH_RECEIPT",
        "CASH_RECEIPT",
        "WIRE_IN",
    }:
        return DEPOSIT

    # -----------------------------------------------------
    # External cash leaving the portfolio
    # -----------------------------------------------------

    if schwab_type in {
        "ACH_DISBURSEMENT",
        "CASH_DISBURSEMENT",
        "WIRE_OUT",
    }:
        return WITHDRAWAL

    # -----------------------------------------------------
    # Everything else
    # -----------------------------------------------------

    return OTHER


# =========================================================
# Normalization
# =========================================================


def normalize_transaction(raw_transaction):
    """
    Convert one raw Schwab transaction into our application's
    Transaction model.
    """

    category = classify_transaction(raw_transaction)

    transfer_items = raw_transaction.get("transferItems", [])

    symbol = None
    quantity = None
    price = None

    # Most of the transactions we care about will contain
    # one transfer item. We use the first item for V1.
    if transfer_items:
        item = transfer_items[0]

        instrument = item.get("instrument", {})

        symbol = instrument.get("symbol")

        quantity = item.get("amount")

        price = item.get("price")

    return Transaction(
        activity_id=raw_transaction.get("activityId"),
        time=raw_transaction.get("time", ""),
        category=category,
        schwab_type=raw_transaction.get("type", ""),
        description=raw_transaction.get("description", ""),
        net_amount=float(
            raw_transaction.get(
                "netAmount",
                0.0,
            )
            or 0.0
        ),
        symbol=symbol,
        quantity=(float(quantity) if quantity is not None else None),
        price=(float(price) if price is not None else None),
    )


# =========================================================
# Summary
# =========================================================


def build_transaction_summary(
    raw_transactions,
    start_time,
    end_time,
):
    """
    Normalize Schwab transactions and build a summary that
    analytics.py can eventually consume.
    """

    summary = TransactionSummary(
        start_time=start_time,
        end_time=end_time,
    )

    for raw_transaction in raw_transactions:
        transaction = normalize_transaction(raw_transaction)

        summary.transactions.append(transaction)

        # -------------------------------------------------
        # Trade
        # -------------------------------------------------

        if transaction.category == TRADE:
            summary.trades.append(transaction)

        # -------------------------------------------------
        # Transfer
        # -------------------------------------------------

        elif transaction.category == TRANSFER:
            summary.transfers.append(transaction)

        # -------------------------------------------------
        # Deposit
        # -------------------------------------------------

        elif transaction.category == DEPOSIT:
            summary.deposits += abs(transaction.net_amount)

        # -------------------------------------------------
        # Withdrawal
        # -------------------------------------------------

        elif transaction.category == WITHDRAWAL:
            summary.withdrawals += abs(transaction.net_amount)

        # -------------------------------------------------
        # Dividend / Interest
        # -------------------------------------------------

        elif transaction.category == INCOME:
            summary.income.append(transaction)

            summary.dividends_and_interest += transaction.net_amount

        # -------------------------------------------------
        # Other
        # -------------------------------------------------

        else:
            summary.other.append(transaction)

    return summary


# =========================================================
# Schwab Retrieval
# =========================================================


def load_transactions(
    start_datetime,
    end_datetime,
):
    """
    Retrieve transactions for every authorized Schwab account
    and return one combined portfolio-level summary.
    """

    client = SchwabClient()

    account_mappings = client.get_account_numbers()

    raw_transactions = []

    start_time = iso_utc(start_datetime)

    end_time = iso_utc(end_datetime)

    for account_mapping in account_mappings:
        account_hash = account_mapping["hashValue"]

        account_transactions = client.get_transactions(
            account_hash=account_hash,
            start_date=start_time,
            end_date=end_time,
        )

        if account_transactions:
            raw_transactions.extend(account_transactions)

    return build_transaction_summary(
        raw_transactions=raw_transactions,
        start_time=start_time,
        end_time=end_time,
    )


# =========================================================
# Display
# =========================================================
