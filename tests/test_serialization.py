from portfolio_agent.domain.portfolio import Account, Portfolio, Position
from portfolio_agent.storage.serialization import portfolio_to_snapshot, snapshot_to_portfolio


def test_portfolio_snapshot_round_trip():
    original = Portfolio(
        total_value=100.0,
        cash=25.0,
        accounts=[
            Account(
                account_type="BROKERAGE",
                total_value=100.0,
                cash=25.0,
                positions=[Position("ABC", "EQUITY", 1.0, 75.0, 75.0)],
            )
        ],
        positions=[Position("ABC", "EQUITY", 1.0, 75.0, 75.0)],
    )

    assert snapshot_to_portfolio(portfolio_to_snapshot(original)) == original
