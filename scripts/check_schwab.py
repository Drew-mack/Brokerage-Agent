"""Verify local Schwab authentication with a read-only API request."""

from portfolio_agent.integrations.schwab import SchwabClient


if __name__ == "__main__":
    accounts = SchwabClient().get_account_numbers()
    print(f"Schwab connection succeeded for {len(accounts)} account(s).")

