#!/usr/bin/env python3
"""Log in and print everything the account exposes: info, summary, positions, pending orders, specs.

    MT5_SERVER=Exness-MT5Trial6 MT5_LOGIN=... MT5_PASSWORD=... python examples/account_overview.py
"""

import logging
import os

from mt5direct import MT5Client

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


def main() -> None:
    with MT5Client.from_server(os.environ.get("MT5_SERVER", "Exness-MT5Trial6")) as client:
        client.login(int(os.environ["MT5_LOGIN"]), os.environ["MT5_PASSWORD"])
        client.get_symbols()

        acct = client.get_account_info()
        print(f"\naccount  {acct.server} / {acct.company} / group {acct.group}")
        print(f"         balance {acct.balance} {acct.currency}, credit {acct.credit}, leverage 1:{acct.leverage}, stopout {acct.stopout_level}%")

        s = client.get_account_summary()
        print(f"summary  equity {s.equity:.2f}  margin {s.margin:.2f}  free {s.free_margin:.2f}  level {s.margin_level:.1f}%  profit {s.profit:.2f}  positions {s.positions_count}")

        positions, pending = client.get_positions_and_orders()
        for p in positions[:10]:
            print(f"position #{p.ticket} {p.type} {p.symbol} {p.volume} @ {p.price_open} -> {p.price_current}  profit {p.profit} swap {p.swap} comm {p.commission} margin {p.margin:.2f}")
        for o in pending[:10]:
            print(f"pending  #{o.ticket} {o.symbol} @ {o.price} t={o.time} '{o.comment}'")

        for name, info in client.get_symbol_info("EURUSD", "XAUUSD").items():
            print(f"spec     {name}: {info.trade_mode}, contract {info.contract_size}, tick {info.tick_size}/{info.tick_value}, "
                  f"vol {info.volume_min}..{info.volume_max} step {info.volume_step}")

        deals, orders = client.get_history()
        print(f"history  {len(deals)} deals, {len(orders)} orders")
        for d in deals[-3:]:
            print(f"deal     #{d.deal} order {d.order} {d.action} {d.entry} {d.symbol} {d.volume} @ {d.price} profit {d.profit} comm {d.commission} swap {d.swap} '{d.comment}'")

        client.login_with_token(int(os.environ["MT5_LOGIN"]))
        print("\ntoken login: ok")


if __name__ == "__main__":
    main()
