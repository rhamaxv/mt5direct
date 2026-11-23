# mt5direct

Standalone MetaTrader 5 client in pure Python. Talks the terminal's native
WebSocket protocol directly to the broker, so no MT5 desktop, no Wine, no
bridge DLL.

## Install

```bash
pip install -e .
```

Requires Python 3.10+, `pycryptodome` and `websocket-client`.

## Quick start

```python
import os
from mt5direct import MT5Client

with MT5Client() as client:
    client.login(int(os.environ["MT5_LOGIN"]), os.environ["MT5_PASSWORD"])
    client.get_symbols()
    client.init_trading()

    acct = client.get_account_info()
    print(acct.balance, acct.currency)

    candles = client.get_candles("EURUSD", "H1", count=100)
    print(candles[-1].close)

    result = client.buy("EURUSD", 0.01)
    print(result.retcode_str, result.deal, result.price)
```

### Live ticks

```python
client.subscribe_by_name("EURUSD", "XAUUSD")
client.on_tick(lambda t: print(t.symbol, t.bid, t.ask))
client.start_tick_listener()
```

### Positions

```python
for p in client.get_positions():
    print(p.ticket, p.type, p.symbol, p.volume, p.price_open)

client.close_all("EURUSD")
```

More in `examples/`.

## API layout

Every operation is available two ways: flat on the client
(`client.buy(...)`) or grouped by domain (`client.trading.buy(...)`).

| Group              | Methods                                                                 |
|--------------------|-------------------------------------------------------------------------|
| `client.auth`      | `login`, `ping`, `reconnect`, `auto_reconnect`                          |
| `client.account`   | `get_account_info`, `init_trading`, `get_history`                       |
| `client.symbols`   | `get_symbols`, `resolve_symbols`, `subscribe`, `subscribe_by_name`, `subscribe_all` |
| `client.market`    | `get_candles`, `on_tick`, `start_tick_listener`, `stop_tick_listener`   |
| `client.trading`   | `buy`, `sell`, `buy_limit`, `sell_limit`, `buy_stop`, `sell_stop`, `modify_sl_tp`, `modify_pending`, `cancel_order`, `close_position`, `trade`, `wait_trade_result` |
| `client.positions` | `get_positions`, `close_all`, `track_positions`                         |

Results are frozen dataclasses from `mt5direct.models`: `AccountInfo`,
`Symbol`, `Tick`, `Candle`, `Position`, `Deal`, `TradeAck`, `TradeResult`.

Order methods return a `TradeResult` when the server confirms execution, the
raw `TradeAck` when the request was rejected up front, or `None` on timeout.

## Package structure

```
src/mt5direct/
  client.py       facade
  services/       one module per domain: auth, account, symbols, market_data, trading, positions
  transport/      WebSocket connection, AES session, message queue
  protocol/       crypto, framing, field serializer, binary reader, record layouts
  parsers/        bytes -> models, pure functions
  models/         dataclasses
  constants/      command ids, order types, retcodes, timeframes, hosts
```

Dependencies point downward only: `client -> services -> transport -> protocol`,
and `services -> parsers -> protocol, models`.

## Tests

```bash
pip install -e '.[dev]'
pytest
```

Tests cover `protocol` and `parsers` with synthetic bytes. `transport` and
`services` need a live server and are exercised by `examples/demo.py`.

## Migrating from `main.py`

The single-file version lives in `legacy/main.py`. Differences:

- Results are dataclasses, not dicts: `tick['bid']` becomes `tick.bid`.
- `client.symbols` is now the symbol service; the symbol list is `client.symbol_list`.
- `connect()`/`login()` raise `ConnectionFailed`/`LoginFailed` (both subclass `ConnectionError`).
- Credentials come from `MT5_LOGIN` / `MT5_PASSWORD` in the examples.
