"""Print the latest stored thesis for selected symbols."""

import argparse

from portfolio_agent.storage.thesis_storage import get_latest_thesis


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("symbols", nargs="+", help="Ticker symbols to inspect")
    args = parser.parse_args()

    for symbol in args.symbols:
        thesis = get_latest_thesis(symbol)
        if thesis is None:
            print(f"{symbol.upper()}: no thesis found")
            continue
        print(f"{symbol.upper()} ({thesis['timestamp']}): {thesis['outlook']}")
        print(thesis["summary"])


if __name__ == "__main__":
    main()

