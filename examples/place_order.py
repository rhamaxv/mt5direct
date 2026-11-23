#!/usr/bin/env python3
"""Open a 0.01-lot EURUSD position, list positions, then close it."""

import os

from mt5direct import MT5Client, TradeResult


def main() -> None:
    with MT5Client() as client:
        client.login(int(os.environ["MT5_LOGIN"]), os.environ["MT5_PASSWORD"])
        client.get_symbols()
        client.init_trading()

        result = client.buy("EURUSD", 0.01, comment="example")
        print("buy:", result)

        if isinstance(result, TradeResult) and result.deal:
            for p in client.get_positions():
                print(f"open: #{p.ticket} {p.type} {p.symbol} {p.volume} @ {p.price_open}")
            closed, total = client.close_all("EURUSD")
            print(f"closed {closed}/{total}")


if __name__ == "__main__":
    main()
