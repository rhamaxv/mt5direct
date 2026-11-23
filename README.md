# mt5direct

[![PyPI](https://img.shields.io/pypi/v/mt5direct)](https://pypi.org/project/mt5direct/)
[![CI](https://github.com/rhamaxv/mt5direct/actions/workflows/ci.yml/badge.svg)](https://github.com/rhamaxv/mt5direct/actions/workflows/ci.yml)
[![Python](https://img.shields.io/pypi/pyversions/mt5direct)](https://pypi.org/project/mt5direct/)
[![License](https://img.shields.io/github/license/rhamaxv/mt5direct)](LICENSE)

Standalone MetaTrader 5 client in pure Python. It speaks the terminal's native
WebSocket protocol directly to the broker's trade server, so there is no MT5
desktop, no Wine, no bridge DLL, and it runs on Linux and macOS.

- Login, account info, symbol list, candles, live ticks
- Market, pending, modify, cancel and close orders
- Open positions, deal history, floating P&L tracking
- Automatic reconnect across the broker's server pool
- Typed results (frozen dataclasses), layered package, offline-testable parsers

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

### Adding a broker

Open your broker's web terminal in a browser and give that page's URL to the
library once. It scans the page for `/terminal` hosts, verifies them, and
remembers them:

```python
from mt5direct import discover_from_url

discover_from_url("https://webterminal.hfm.com/en/mt5")
# [Endpoint(host='live.webterminal-hfm.com', port=1951, server='HFMarketsGlobal-Live1', ...), ...]

MT5Client.from_server("HFMarketsGlobal-Live1")   # works from now on
```

Then add the entries to `src/mt5direct/data/webterminals.json` and open a pull
request so everyone gets them. Or skip all of it and pass the host directly:

```python
client = MT5Client(host="live3.webterminal-hfm.com:1951")
```

### Verified brokers

| Broker | Servers | Hosts |
|--------|---------|-------|
| Exness | all `Exness-MT5*` | `<code>.exwebterm.com` (pattern) |
| HFM | `HFMarketsGlobal-Live1..20`, `HFMarkets-Live12`, `HFMarketsGlobal-Demo4` | `live*.webterminal-hfm.com:1951` |
| Finex | `FinexBisnisSolusi-Real`, `-Demo` | `real-terminal.finex.co.id`, `demo-terminal.finex.co.id` |
| MetaQuotes | `MetaQuotes-Demo` | `web.metatrader.app` |

Reconnects (`client.reconnect(...)` and the tick listener's automatic reconnect)
try the resolved host first, then the built-in `TRADE_HOSTS` pool.

Environment variables: `MT5DIRECT_CACHE_DIR` overrides the cache directory,
`MT5DIRECT_OFFLINE=1` skips the GitHub refresh.

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
acct = client.get_account_info()        # AccountInfo | None
deals, orders = client.get_history()    # list[Deal], list[HistoryOrder]
deals, _ = client.get_history(from_ts=1700000000, to_ts=1700600000)
```

### Symbols

```python
for s in client.get_symbols():
    print(s.name, s.digits, s.path)

eurusd = client.symbol_map["EURUSD"]    # Symbol
```

### Candles

```python
candles = client.get_candles("XAUUSD", "M15", count=500)
candles = client.get_candles("XAUUSD", "D1", from_ts=1690000000, to_ts=1700000000)
```

Timeframes: `M1 M2 M3 M4 M5 M6 M10 M12 M15 M20 M30 H1 H2 H3 H4 H6 H8 H12 D1 W1 MN1`
(see `mt5direct.TIMEFRAMES`). Up to `count` most recent candles are returned.

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
    print(p.ticket, p.type, p.symbol, p.volume, p.price_open, p.sl, p.tp)

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

## API overview

Everything is reachable two ways: flat on the client (`client.buy(...)`) or
grouped by domain (`client.trading.buy(...)`). Both call the same code.

| Group              | Methods |
|--------------------|---------|
| `client`           | `from_server`, `connect`, `close`, `recv_any`, `host`, `address`, `endpoint`, `server_id`, `symbol_list`, `symbol_map`, `ta_to_sym` |
| `mt5direct.discovery` | `list_servers`, `resolve_server`, `discover_from_url`, `inspect_host`, `load_registry`, `candidate_addresses` |
| `client.auth`      | `login`, `ping`, `reconnect`, `auto_reconnect` |
| `client.account`   | `get_account_info`, `init_trading`, `get_history` |
| `client.symbols`   | `get_symbol_types`, `get_symbols`, `resolve_symbols`, `subscribe`, `subscribe_by_name`, `subscribe_all` |
| `client.market`    | `get_candles`, `parse_tick`, `parse_ticks`, `on_tick`, `start_tick_listener`, `stop_tick_listener` |
| `client.trading`   | `trade`, `wait_trade_result`, `buy`, `sell`, `buy_limit`, `sell_limit`, `buy_stop`, `sell_stop`, `modify_sl_tp`, `modify_pending`, `cancel_order`, `close_position`, `close_by_order` |
| `client.positions` | `get_positions`, `close_all`, `track_positions` |

Full signatures and field lists: [docs/api.md](docs/api.md).

## Return values and errors

Results are frozen dataclasses from `mt5direct.models`:

| Model          | Returned by |
|----------------|-------------|
| `AccountInfo`  | `get_account_info` |
| `Symbol`       | `get_symbols`, `symbol_map`, `ta_to_sym` |
| `Tick`         | tick callbacks, `parse_ticks` |
| `Candle`       | `get_candles` |
| `Position`     | `get_positions` |
| `PositionPnL`  | `track_positions` callback |
| `Deal`, `HistoryOrder` | `get_history` |
| `TradeAck`     | `trade`, and order helpers when rejected up front |
| `TradeResult`  | `wait_trade_result`, and order helpers on execution |
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
