# Architecture

```
src/mt5direct/
├── client.py          MT5Client facade
├── exceptions.py
├── constants/         command ids, order constants, retcodes, timeframes, hosts
├── protocol/          bytes only: crypto, framing, serializer, reader, layouts
├── transport/         WebSocketTransport, Session (handshake, key, queue, lock)
├── models/            frozen dataclasses
├── parsers/           bytes -> models, pure functions
└── services/          one class per domain, built on Session + parsers
```

## Dependency rule

Imports only point downward:

```
client ──► services ──► transport ──► protocol
               │
               └──────► parsers ──► protocol, models
```

`models` and `protocol` import nothing from above them. That is what makes
`parsers` testable with synthetic bytes and no socket.

## A call through the stack

`client.buy("EURUSD", 0.01)`:

1. `client.py` delegates to `TradingService.buy`.
2. `services/trading.py` builds the field list and calls `serialize()`
   (`protocol/serializer.py`), then `BaseService.request(CMD_TRADE, payload)`.
3. `transport/session.py` wraps the payload with `encode_frame()`
   (`protocol/framing.py` + `protocol/crypto.py`) and writes it to the
   WebSocket, then reads frames until one with `cmd == CMD_TRADE` arrives,
   queueing anything else.
4. `parsers/trade.py` turns the reply into a `TradeAck`.
5. If `ack.retcode == 0`, `TradingService.wait_trade_result` drains
   `Session.recv_any()` until `parsers/trade.py::parse_trade_result` yields a
   final `TradeResult`.

## Shared state

`services/base.py::ClientState` holds what services share: the symbol table
(`symbols`, `symbol_map`, `ta_to_sym`) and stored credentials for
`auto_reconnect`. Each service receives the same `Session` and `ClientState`;
services that need another service (`AuthService` → symbols/account,
`MarketDataService` → auth, `PositionService` → trading) receive it in the
constructor. `client.py` is the only place that wires them.

## Threading

`Session` guards its frame queue with a lock. `start_tick_listener` runs a
daemon thread that calls `recv_any`; calling request/reply methods from
another thread at the same time is possible but the reply may be consumed by
the listener and discarded (it only looks at `CMD_TICK`). Keep request/reply
traffic on one thread, or stop the listener first.

## Testing strategy

- `tests/protocol/`: serializer, reader, crypto round-trip, framing.
- `tests/parsers/`: every parser against hand-built records, including the
  edge cases (unknown symbol id, trailing bytes, placeholder SL/TP, short
  trade-result frames, in-flight codes).
- `transport/` and `services/` are exercised live by `examples/demo.py`.
