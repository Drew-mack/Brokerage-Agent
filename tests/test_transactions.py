from portfolio_agent.domain.transactions import (
    DEPOSIT,
    INCOME,
    TRADE,
    TRANSFER,
    classify_transaction,
)


def test_transaction_classification_is_conservative():
    assert classify_transaction({"type": "TRADE"}) == TRADE
    assert classify_transaction({"type": "DIVIDEND_OR_INTEREST"}) == INCOME
    assert classify_transaction({"type": "ACH_RECEIPT"}) == DEPOSIT
    assert classify_transaction({"type": "RECEIVE_AND_DELIVER"}) == TRANSFER
