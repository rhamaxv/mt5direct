#!/usr/bin/env python3
"""End-to-end protocol walkthrough: connect, login, symbols, ticks, trade.

Set MT5_LOGIN and MT5_PASSWORD in the environment before running.
"""

import datetime
import os
import struct
import sys
import time

from mt5direct import MT5Client, ORDER_SELL
from mt5direct.constants import CMD_TICK, RETCODE_DONE
from mt5direct.protocol.layouts import TICK_RECORD_SIZE


def _credentials():
    try:
        return int(os.environ['MT5_LOGIN']), os.environ['MT5_PASSWORD']
    except KeyError:
        sys.exit("Set MT5_LOGIN and MT5_PASSWORD first.")


def _collect_ticks(client, seconds, tick_count, ticked_ta):
    start = time.time()
    while time.time() - start < seconds:
        msg = client.recv_any(timeout=2)
        if msg and msg.cmd == CMD_TICK:
            z = msg.payload
            off = 0
            while off + TICK_RECORD_SIZE <= len(z):
                ticked_ta.add(struct.unpack('<I', z[off:off + 4])[0])
                tick_count += 1
                off += TICK_RECORD_SIZE
    return tick_count


def _find_positions_in_init_payload(z4, sym_names):
    """Heuristic scan of the raw init-trading payload for (symbol, ticket) pairs."""
    found = []
    for sn in sym_names:
        enc = (sn + '\x00').encode('utf-16-le')
        idx = 0
        while True:
            pos = z4.find(enc, idx)
            if pos == -1:
                break
            if pos >= 24:
                ticket = struct.unpack('<q', z4[pos - 24:pos - 16])[0]
                if 1000000000 < ticket < 99999999999:
                    found.append((sn, ticket))
            idx = pos + 2
    seen = set()
    unique = []
    for sn, t in found:
        if t not in seen:
            seen.add(t)
            unique.append((sn, t))
    return unique


def main():
    login_id, password = _credentials()
    utc_now = datetime.datetime.now(datetime.timezone.utc)

    print("=== MT5 Standalone Client ===")
    print(f"UTC: {utc_now.strftime('%Y-%m-%d %H:%M:%S')} ({utc_now.strftime('%A')})\n")

    client = MT5Client()

    print(f"[1] Connecting to {client.host}...")
    client.connect()
    print("    Connected\n")

    print(f"[2] Login as {login_id}...")
    client.login(login_id, password)
    print("    LOGIN OK\n")

    print("[3] Account info...")
    acct = client.get_account_info()
    bal = acct.balance if acct else '?'
    cur = acct.currency if acct else '?'
    print(f"    Balance: {bal} {cur}\n")

    print("[4] Loading symbols...")
    client.get_symbol_types()
    symbols = client.get_symbols()
    print(f"    {len(symbols)} symbols loaded\n")

    print("[5] Init trading...")
    resp4 = client.init_trading()
    z4 = resp4.payload if resp4 else b''
    print(f"    OK ({len(z4)} bytes)")
    t0 = time.time()
    while time.time() - t0 < 3:
        client.recv_any(timeout=1)

    unique_pos = _find_positions_in_init_payload(z4, {s.name for s in symbols})
    if unique_pos:
        print(f"    Found {len(unique_pos)} open positions across {len({s for s, _ in unique_pos})} symbols")
        n_closed = 0
        for sn, ticket in unique_pos:
            ack = client.trade(ORDER_SELL, sn, 0.01, position=ticket)
            if ack:
                if ack.retcode == 0:
                    wr = client.wait_trade_result(timeout=5)
                    if wr and wr.retcode == RETCODE_DONE:
                        n_closed += 1
                elif ack.retcode == RETCODE_DONE:
                    n_closed += 1
        print(f"    Closed {n_closed}/{len(unique_pos)} positions")
    else:
        print("    No open positions found")
    print()

    print("[6] Resolve + Subscribe ALL symbols...")
    n, resolve_data = client.subscribe_all()
    rb = len(resolve_data)
    print(f"    resolve: {n} symbols, {rb:,} bytes ({rb // n} bytes/symbol)")
    print("    subscribe: single call\n")

    n_sym = len(symbols)
    print("[7] Tick stream - collecting realtime data...")
    all_ta_set = {s.ta for s in symbols}
    ticked_ta = set()
    tick_count = _collect_ticks(client, 30, 0, ticked_ta)

    missing_ta = all_ta_set - ticked_ta
    if missing_ta:
        print(f"    Phase 1: {tick_count} ticks, {len(ticked_ta)} symbols. Re-subscribing {len(missing_ta)}...")
        client.resolve_symbols(list(missing_ta))
        client.subscribe(list(missing_ta))
        tick_count = _collect_ticks(client, 30, tick_count, ticked_ta)
        still_missing = all_ta_set - ticked_ta
        if still_missing:
            print(f"    Phase 2: re-resolve + re-subscribe {len(still_missing)} symbols...")
            for ta in still_missing:
                client.resolve_symbols([ta])
                client.subscribe([ta])
            tick_count = _collect_ticks(client, 15, tick_count, ticked_ta)

    print(f"    {tick_count} ticks decoded, {len(ticked_ta)}/{n_sym} symbols received realtime data\n")

    print("[8] Trade: BUY 0.01 EURUSD...")
    buy = client.buy('EURUSD', 0.01, comment='standalone')
    print(f"    {_fmt(buy)}\n")

    print("[9] Trade: SELL 0.01 EURUSD...")
    sell = client.sell('EURUSD', 0.01, comment='standalone')
    print(f"    {_fmt(sell)}\n")

    print(f"[10] Server verification: volume=0 probe to all {n_sym} symbols...")
    n_responded = sum(1 for s in symbols if client.trade(0, s.name, 0.0))
    print(f"    {n_responded}/{n_sym} symbols responded\n")
    client.close()

    print("=== SUMMARY ===")
    print(f"account:   balance {bal} {cur}")
    print(f"symbols:   {n_sym}")
    print(f"ticks:     {tick_count} ticks, {len(ticked_ta)}/{n_sym} symbols")
    print(f"trade:     BUY {_fmt(buy)} | SELL {_fmt(sell)}")
    print(f"verify:    {n_responded}/{n_sym} symbols got server response")


def _fmt(result):
    if result is None:
        return "no response"
    rc = result.retcode_str or '?'
    deal = getattr(result, 'deal', 0)
    price = getattr(result, 'price', 0)
    return f"{rc}({result.retcode}) deal #{deal} @ {price}"


if __name__ == "__main__":
    main()
