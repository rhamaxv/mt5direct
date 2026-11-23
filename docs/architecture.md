# Architecture

```
src/mt5direct/
├── client.py          MT5Client facade
├── aio.py             AsyncMT5Client (to_thread wrapper)
├── discovery.py       server name -> verified web terminal host (HTTP, no protocol code)
├── data/              webterminals.json registry shipped with the package
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

`Session` has two reading modes. Without a background reader, `recv` and
`recv_any` read the socket directly. When `start_tick_listener` runs, its
thread calls `Session.attach_reader` and becomes the only socket reader; a
`recv(cmd)` from any other thread registers as a waiter and blocks on a
`Condition` until the listener hands it the matching frame through the queue.
The listener's `recv_any` never returns frames for awaited commands. This is
what makes `start_heartbeat` (pings from a third thread) and trading calls from
the main thread safe while the listener is running.

## Testing strategy

- `tests/protocol/`: serializer, reader, crypto round-trip, framing.
- `tests/parsers/`: every parser against hand-built records, including the
  edge cases (unknown symbol id, trailing bytes, placeholder SL/TP, short
  trade-result frames, in-flight codes).
- `transport/` and `services/` are exercised live by `examples/demo.py`.
