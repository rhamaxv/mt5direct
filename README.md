# mt5direct

[![PyPI](https://img.shields.io/pypi/v/mt5direct)](https://pypi.org/project/mt5direct/)
[![CI](https://github.com/rhamaxv/mt5direct/actions/workflows/ci.yml/badge.svg)](https://github.com/rhamaxv/mt5direct/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/mt5direct)](https://pypi.org/project/mt5direct/)
[![License](https://img.shields.io/github/license/rhamaxv/mt5direct)](LICENSE)

Standalone MetaTrader 5 client in pure Python. It speaks the terminal's native
WebSocket protocol directly to the broker's trade server, so there is no MT5
desktop, no Wine, no bridge DLL, and it runs on Linux and macOS.

- Login, account info and live equity/margin summary
- Symbol list and trading specifications (contract size, volumes, trade mode)
- Candles (optionally as a pandas DataFrame), live ticks, trade and position events
- Market, pending, modify, cancel and close orders; open positions and pending orders
- Deal and order history with order and position ids, prices, volumes and comments
- Heartbeat and automatic reconnect that re-logs in and re-subscribes
- Sync and asyncio clients, typed results (frozen dataclasses), offline-testable parsers

**Contents**

- [Install](#install)
- [Choosing a server](#choosing-a-server)
- [Quick start](#quick-start)
- [Usage](#usage)
- [API overview](#api-overview)
- [Return values and errors](#return-values-and-errors)
- [Documentation](#documentation)
- [Development](#development)
- [Releasing](#releasing)
- [Disclaimer](#disclaimer)

## Install

```bash
pip install mt5direct
```

Requires Python 3.10+. Dependencies (`pycryptodome`, `websocket-client`) are
installed automatically.

From source:

```bash
git clone https://github.com/rhamaxv/mt5direct
cd mt5direct
pip install -e '.[dev]'
```

## Choosing a server

Same flow as the MT5 app: search the company, pick a server from the list, connect.

```python
from mt5direct import MT5Client, list_servers

list_servers("finex")
# ['FinexBisnisSolusi-Demo', 'FinexBisnisSolusi-Real']

client = MT5Client.from_server("FinexBisnisSolusi-Real")
client.connect()
client.login(login, password)
```

`list_servers` queries MetaQuotes' public directory (about 2,800 MT5 servers).
`from_server` looks the host up in the web terminal registry, verifies it, and
connects. `MT5Client(server="...")` does the same.

### How a name becomes a host

Every broker runs its own MT5 Web Terminal, and each terminal host serves exactly
one trade server, which it announces in `window.__terminal_params` on its
`/terminal` page. MetaQuotes publishes server *names* but never these hosts, so
the library carries a registry and verifies every candidate before using it:

1. **Registry lookup**: a JSON file bundled with the package
   (`src/mt5direct/data/webterminals.json`), refreshed from GitHub once a day and
   cached under `~/.cache/mt5direct/`. Exact entries
   (`FinexBisnisSolusi-Real` → `real-terminal.finex.co.id`,
   `HFMarketsGlobal-Live3` → `live3.webterminal-hfm.com:1951`) and broker patterns
   (`Exness` → `{code}.exwebterm.com`).
2. **Guesses** for brokers not in the registry: a few host patterns that brokers
   commonly use.
3. **Verification**: each candidate's `/terminal` page must announce exactly the
   requested server. A verified guess is remembered in
   `~/.cache/mt5direct/learned.json` so the next call is instant.

If nothing verifies, `ServerNotFound` tells you what was tried and how to fix it.

### What does not work, and why

Verified against the live services on 2026-11-23, so nobody has to re-explore:

- `web.metatrader.app` serves only `MetaQuotes-Demo`. Its `?servers=` parameter is
  ignored; it is not a universal proxy.
- MetaQuotes' hosted web terminal (`metatraderweb.app/trade`) uses an older,
  different protocol through `gwt*.mql5.com`, and only opted-in brokers are
  enabled there. Exness is not.
- The public directory lists names only, never hosts. The new web terminal's
  JavaScript makes no HTTP calls at all; it only opens `wss://<its own host>/terminal`.
- A broker that does not offer an MT5 Web Terminal cannot be reached with this
  protocol by any means.

## Quick start

```python
import os
from mt5direct import MT5Client

with MT5Client.from_server("Exness-MT5Trial6") as client:
    client.login(int(os.environ["MT5_LOGIN"]), os.environ["MT5_PASSWORD"])
    client.get_symbols()      # download the symbol table (required once)
    client.init_trading()     # open the trading session

    acct = client.get_account_info()
    print(acct.balance, acct.currency)

    candles = client.get_candles("EURUSD", "H1", count=100)
    print(candles[-1].close)

    result = client.buy("EURUSD", 0.01)
    print(result.retcode_str, result.deal, result.price)
```

`with` calls `connect()` on entry and `close()` on exit. Without `with`, call
them yourself.

## Usage

### Session setup

The three calls after `connect()` are always the same:

```python
client.login(login_id, password)   # raises LoginFailed on rejection
client.get_symbols()               # fills client.symbol_list / symbol_map / ta_to_sym
client.init_trading()              # server starts sending trade events
```

Skipping `get_symbols()` leaves ticks unnamed (`symbol="#<id>"`) and
`subscribe_by_name` with nothing to look up.

### Account

```python
acct = client.get_account_info()        # balance, credit, currency, leverage, group, server, company, stopout_level
summary = client.get_account_summary()  # + equity, margin, free_margin, margin_level, profit from open positions
deals, orders = client.get_history()    # list[Deal], list[HistoryOrder]
deals, _ = client.get_history(from_ts=1700000000, to_ts=1700600000)
```

### Symbols

```python
for s in client.get_symbols():
    print(s.name, s.digits, s.path)

eurusd = client.symbol_map["EURUSD"]    # Symbol

info = client.get_symbol_info("EURUSD", "XAUUSD")["XAUUSD"]   # SymbolInfo
info.contract_size, info.volume_min, info.volume_step, info.trade_mode, info.tick_value
```

### Candles

```python
candles = client.get_candles("XAUUSD", "M15", count=500)
candles = client.get_candles("XAUUSD", "D1", from_ts=1690000000, to_ts=1700000000)
```

Timeframes: `M1 M2 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1`
(see `mt5direct.TIMEFRAMES`). Up to `count` most recent candles are returned.

With `pip install 'mt5direct[pandas]'`, `client.get_candles_df(...)` returns a
DataFrame indexed by UTC time.

### Live ticks

```python
client.subscribe_by_name("EURUSD", "XAUUSD")
# or everything: client.subscribe_all()

def on_tick(tick):
    print(tick.symbol, tick.bid, tick.ask, tick.spread)

client.on_tick(on_tick)
thread = client.start_tick_listener()   # daemon thread; reconnects on error
...
client.stop_tick_listener()
```

Other events from the same listener:

```python
client.on_trade(lambda r: print(r.retcode_str, r.deal, r.price))     # every execution report
client.on_position_change(lambda positions: print(len(positions)))   # server pushed a new position list
```

Keep the session alive and self-healing while the listener runs:

```python
client.start_heartbeat(interval=30)   # pings; on failure reconnects, re-logs in with the token, re-subscribes
```

Requests from your main thread (`buy`, `ping`, `get_positions`, ...) are safe while
the listener is running: replies are routed back to the caller through the session
queue.

If you prefer to drive the loop yourself, read frames directly:

```python
from mt5direct.constants import CMD_TICK

frame = client.recv_any(timeout=1)
if frame and frame.cmd == CMD_TICK:
    for tick in client.market.parse_ticks(frame.payload):
        ...
```

### Orders

```python
client.buy("EURUSD", 0.01, sl=1.0800, tp=1.1000, comment="bot")
client.sell("EURUSD", 0.01)

client.buy_limit("EURUSD", 0.01, price=1.0850)
client.sell_stop("EURUSD", 0.01, price=1.0800, sl=1.0850)

client.modify_sl_tp("EURUSD", position_ticket, sl=1.0820, tp=1.0950)
client.modify_pending("EURUSD", order_ticket, price=1.0860)
client.cancel_order("EURUSD", order_ticket)
```

Lots are plain floats (`0.01`). Prices are plain floats in the symbol's own
scale. `0.0` for `sl`/`tp` means "not set".

### Positions

```python
for p in client.get_positions():
    print(p.ticket, p.type, p.symbol, p.volume, p.price_open, p.profit, p.margin)

for o in client.get_pending_orders():
    print(o.ticket, o.type, o.symbol, o.price, o.volume, o.comment)

positions, pending = client.get_positions_and_orders()   # one round-trip

client.close_position("EURUSD", ticket, lots=0.01, pos_type="BUY")
closed, total = client.close_all()            # every position
closed, total = client.close_all("EURUSD")    # one symbol

def on_pnl(rows):
    for r in rows:
        print(r.position.ticket, r.current_price, round(r.pnl, 2))

client.track_positions(duration=60, callback=on_pnl)
```

### Low-level trade request

All order helpers call `client.trade(...)`, which sends one raw request and
returns the server's acknowledgement. Use it when you need a combination the
helpers do not cover:

```python
from mt5direct import ORDER_BUY, TRADE_ACTION_DEAL, FILLING_IOC

ack = client.trade(ORDER_BUY, "EURUSD", 0.05, exec_mode=TRADE_ACTION_DEAL,
                   filling_ea=FILLING_IOC, deviation=20)
if ack and ack.retcode == 0:
    result = client.wait_trade_result(timeout=30)
```

### asyncio

```python
from mt5direct import AsyncMT5Client

async with AsyncMT5Client.from_server("Exness-MT5Trial6") as client:
    await client.login(login, password)
    await client.get_symbols()
    acct = await client.get_account_summary()
    result = await client.buy("EURUSD", 0.01)
```

Every blocking call runs in a worker thread; callbacks and `start_*`/`stop_*`
methods are plain functions.

## API overview

Everything is reachable two ways: flat on the client (`client.buy(...)`) or
grouped by domain (`client.trading.buy(...)`). Both call the same code.

| Group              | Methods |
|--------------------|---------|
| `client`           | `from_server`, `connect`, `close`, `recv_any`, `host`, `address`, `endpoint`, `server_id`, `symbol_list`, `symbol_map`, `ta_to_sym` |
| `mt5direct.discovery` | `list_servers`, `resolve_server`, `discover_from_url`, `inspect_host`, `load_registry`, `candidate_addresses` |
| `client.auth`      | `login`, `login_with_token`, `ping`, `reconnect`, `auto_reconnect` |
| `client.account`   | `get_account_info`, `get_account_summary`, `init_trading`, `get_history` |
| `client.symbols`   | `get_symbol_types`, `get_symbols`, `get_symbol_info`, `resolve_symbols`, `subscribe`, `subscribe_by_name`, `subscribe_all` |
| `client.market`    | `get_candles`, `get_candles_df`, `on_tick`, `on_trade`, `on_position_change`, `start_tick_listener`, `stop_tick_listener`, `start_heartbeat`, `stop_heartbeat` |
| `client.trading`   | `trade`, `wait_trade_result`, `buy`, `sell`, `buy_limit`, `sell_limit`, `buy_stop`, `sell_stop`, `modify_sl_tp`, `modify_pending`, `cancel_order`, `close_position`, `close_by_order` |
| `client.positions` | `get_positions`, `get_pending_orders`, `get_positions_and_orders`, `close_all`, `track_positions` |

Full signatures and field lists: [docs/api.md](docs/api.md).

## Return values and errors

Results are frozen dataclasses from `mt5direct.models`:

| Model          | Returned by |
|----------------|-------------|
| `AccountInfo`  | `get_account_info` |
| `AccountSummary` | `get_account_summary` |
| `SymbolInfo`   | `get_symbol_info` |
| `Symbol`       | `get_symbols`, `symbol_map`, `ta_to_sym` |
| `Tick`         | tick callbacks, `parse_ticks` |
| `Candle`       | `get_candles` |
| `Position`     | `get_positions`, `on_position_change` |
| `PendingOrder` | `get_pending_orders` |
| `PositionPnL`  | `track_positions` callback |
| `Deal`, `HistoryOrder` | `get_history` |
| `TradeAck`     | `trade`, and order helpers when rejected up front |
| `TradeResult`  | `wait_trade_result`, order helpers on execution, `on_trade` |
| `Frame`        | `recv_any`, `init_trading`, `ping`, `resolve_symbols` |

Order helpers (`buy`, `sell`, `close_position`, ...) return:

- `TradeResult` when the server reports execution (`retcode` 10009 or 10011) or a
  final rejection (any other non-transient code);
- `TradeAck` when the request was refused before reaching the dealer
  (`ack.retcode != 0`);
- `None` when nothing came back within the timeout.

Exceptions, all subclasses of `mt5direct.MT5Error`:

| Exception          | Raised by | Meaning |
|--------------------|-----------|---------|
| `ServerNotFound`   | `MT5Client(server=...)`, `resolve_server` | No web terminal host announces that server name |
| `ConnectionFailed` | `connect` | WebSocket opened but the hello handshake failed |
| `LoginFailed`      | `login`   | Server rejected the credentials |

Both also subclass `ConnectionError`. Read-style calls (`get_candles`,
`get_positions`, ...) never raise on timeout; they return `None` or an empty
list. Return codes are in `mt5direct.RETCODES`; see
[docs/errors.md](docs/errors.md).

## Documentation

| Document | Contents |
|----------|----------|
| [docs/api.md](docs/api.md) | Every public method with signature, parameters and return type; every model with its fields |
| [docs/protocol.md](docs/protocol.md) | Wire format: framing, encryption, handshake, command ids, record layouts |
| [docs/errors.md](docs/errors.md) | Exceptions, `None`/empty returns, full return-code table |
| [docs/architecture.md](docs/architecture.md) | Package layers, dependency rules, how a call travels through the stack |
| [docs/contributing.md](docs/contributing.md) | Dev setup, tests, commit format, adding a parser or command |
| [examples/](examples/) | `demo.py` (full walkthrough), `find_server.py` (search → pick → connect), `stream_ticks.py`, `place_order.py` |

## Development

```bash
pip install -e '.[dev]'
pytest
```

Tests cover `protocol` and `parsers` with synthetic bytes and need no network.
`transport` and `services` need a live server; run `examples/demo.py` with
`MT5_LOGIN` and `MT5_PASSWORD` set.

## Releasing

1. Bump `version` in `pyproject.toml`.
2. Commit, tag and push:

```bash
git tag v0.1.1 && git push origin main --tags
```

The `Publish to PyPI` workflow runs the tests, checks that the tag matches the
version, builds, and uploads through PyPI Trusted Publishing.

## Disclaimer

This library implements a reverse-engineered protocol and is not affiliated
with or endorsed by MetaQuotes Ltd. Use it with demo accounts first, read your
broker's terms, and trade at your own risk.
