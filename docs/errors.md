# Errors and return codes

## Exceptions

```
MT5Error (Exception)
├── ServerNotFound                            raised by MT5Client(server=...) / resolve_server()
├── ConnectionFailed (also ConnectionError)   raised by connect()
├── ConnectionLost   (also ConnectionError)   raised by recv_any() when the socket dies mid-session
└── LoginFailed      (also ConnectionError)   raised by login()
```

`ValueError` is raised by `get_candles` for an unknown timeframe name.
Everything else from the standard library (`socket.timeout`,
`websocket.WebSocketException`, ...) can surface from `connect()` and from
`Session.send()` if the socket is gone.

## Calls that return None or empty instead of raising

| Call | On timeout / bad status |
|------|-------------------------|
| `get_account_info` | `None` |
| `get_symbols` | `[]` |
| `get_candles` | `[]` |
| `get_positions` | `[]` |
| `get_history` | `([], [])` |
| `init_trading`, `ping`, `resolve_symbols`, `get_symbol_types` | `None` |
| `trade` | `None` |
| `wait_trade_result` | `None` |
| `buy`, `sell`, pending, modify, close helpers | `None`, or a `TradeAck` with non-zero `retcode` |
| `reconnect`, `auto_reconnect` | `False` |

## Reading an order result

```python
from mt5direct import TradeAck, TradeResult, RETCODE_DONE, RETCODE_DONE_PARTIAL

r = client.buy("EURUSD", 0.01)
if r is None:
    ...                       # no reply within 30 s
elif isinstance(r, TradeAck):
    print("rejected:", r.retcode_str)        # e.g. INVALID_VOLUME
elif r.retcode in (RETCODE_DONE, RETCODE_DONE_PARTIAL):
    print("filled", r.deal, r.price)
else:
    print("failed:", r.retcode_str)          # e.g. NO_MONEY, MARKET_CLOSED
```

## Return codes

`mt5direct.RETCODES` maps code to name; `retcode_name(code)` returns
`UNKNOWN_<code>` for anything else.

| Code | Name | Meaning |
|------|------|---------|
| 0 | PENDING | Request queued; wait for the result event |
| 1 | OK | |
| 10001 | ON_THE_WAY | In progress (skipped by `wait_trade_result`) |
| 10002 | ACCEPTED | In progress |
| 10003 | PROCESSED | In progress |
| 10004 | REQUOTE | Price changed, resend |
| 10005 | PRICES | |
| 10006 | REJECTED | Dealer rejected |
| 10007 | CANCELED | Cancelled by trader |
| 10008 | PLACED | Pending order placed |
| 10009 | DONE | Executed |
| 10011 | DONE_PARTIAL | Partially executed |
| 10012 | TIMEOUT | |
| 10013 | INVALID | Malformed request |
| 10014 | INVALID_VOLUME | |
| 10015 | INVALID_PRICE | |
| 10016 | INVALID_SLTP | Stops too close or on wrong side |
| 10017 | TRADE_DISABLED | |
| 10018 | MARKET_CLOSED | |
| 10019 | NO_MONEY | Insufficient margin |
| 10020 | PRICE_CHANGED | |
| 10021 | OFF_QUOTES | |
| 10023 | ORDER_LOCKED | |
| 10024 | LONG_ONLY | |
| 10026 | ALGO_DISABLED_SERVER | Algo trading off on server |
| 10027 | ALGO_DISABLED_CLIENT | |
| 10030 | UNSUPPORTED_FILLING | Try another `filling_ea` |
| 10033 | ORDERS_LIMIT | |
| 10034 | VOLUME_LIMIT | |
| 10035 | INVALID_ORDER_TYPE | |
| 10036 | INVALID_ORDER | |
| 10038 | POSITION_NOT_FOUND | |
| 10040 | LIMIT_POSITIONS | |
| 10041 | NO_CHANGES | Modify with identical values |
| 10042 | CONNECTION_LOST | |
| 10043 | FREQUENT_REQUESTS | Rate-limited |
