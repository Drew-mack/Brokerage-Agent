from portfolio_agent.domain.portfolio import Portfolio


def test_portfolio_normalizes_accounts_and_positions():
    portfolio = Portfolio.from_schwab(
        [
            {
                "securitiesAccount": {
                    "type": "IRA",
                    "currentBalances": {
                        "liquidationValue": 1250,
                        "cashBalance": 250,
                    },
                    "positions": [
                        {
                            "instrument": {"symbol": "VOO", "assetType": "ETF"},
                            "longQuantity": 2,
                            "shortQuantity": 0,
                            "averagePrice": 500,
                            "marketValue": 1000,
                        }
                    ],
                }
            }
        ]
    )

    assert portfolio.total_value == 1250.0
    assert portfolio.cash == 250.0
    assert portfolio.positions[0].symbol == "VOO"
    assert portfolio.positions[0].quantity == 2.0

