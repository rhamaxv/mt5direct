#!/usr/bin/env python3
"""Print live ticks for a few symbols for 30 seconds."""

import os
import time

from mt5direct import MT5Client, Tick

SYMBOLS = ("EURUSD", "XAUUSD")


def on_tick(tick: Tick) -> None:
    print(f"{tick.symbol:10} bid={tick.bid:<12} ask={tick.ask:<12} spread={tick.spread}")


def main() -> None:
    with MT5Client.from_server(os.environ.get("MT5_SERVER", "Exness-MT5Trial6")) as client:
        client.login(int(os.environ["MT5_LOGIN"]), os.environ["MT5_PASSWORD"])
        client.get_symbols()
        client.init_trading()
        client.subscribe_by_name(*SYMBOLS)

        client.on_tick(on_tick)
        client.start_tick_listener()
        time.sleep(30)
        client.stop_tick_listener()


if __name__ == "__main__":
    main()
