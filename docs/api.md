# API reference

All examples assume:

```python
from mt5direct import MT5Client
client = MT5Client(host="...")
client.connect()
```

Every method below exists both on `client` and on the domain object named in
the heading. `Optional[X]` means `X` or `None`.

## MT5Client

```python
MT5Client(host: str | None = None, server: str | None = None)
MT5Client.from_server(server: str) -> MT5Client
```

`server` is a trade server name (`'Exness-MT5Trial6'`); it is resolved and verified
with `discovery.resolve_server` and may raise `ServerNotFound`. `host` (`'host'` or
`'host:port'`) connects to a web terminal host directly and wins if both are given. With neither, `TRADE_HOSTS[0]`
is used. The port and path are fixed.

| Member | Type | Description |
|--------|------|-------------|
| `connect()` | `None` | Open the socket and run the hello handshake. Raises `ConnectionFailed`. |
| `close()` | `None` | Close the socket. Safe to call twice. |
| `recv_any(timeout=5)` | `Optional[Frame]` | Next frame from the queue or the wire. |
| `host` | `str` | Current server host. Assigning accepts `host` or `host:port`. |
| `address` | `str` | `host` or `host:port`. |
| `endpoint` | `Optional[Endpoint]` | Resolved endpoint when built from a server name. |
| `server_id` | `int` | Server id from the hello reply. |
| `symbol_list` | `list[Symbol]` | Symbols from the last `get_symbols()`. |
| `symbol_map` | `dict[str, Symbol]` | Name to symbol. |
| `ta_to_sym` | `dict[int, Symbol]` | Server symbol id to symbol. |
| `session` | `Session` | Transport layer, for advanced use. |

`MT5Client` is a context manager: `__enter__` calls `connect()`, `__exit__` calls `close()`.

## client.auth

### `login(login_id: int, password: str) -> Frame`

Authenticate. Stores the credentials for `auto_reconnect`. Raises `LoginFailed`.

### `ping() -> Optional[Frame]`

Round-trip to the server, 5 s timeout.

### `reconnect(login_id=None, password=None) -> bool`

Close, then try the resolved server host (if any) followed by each host in
`TRADE_HOSTS`; log in if credentials are given. Returns `True` on the first host that works. Does not re-download
symbols or re-subscribe.

### `auto_reconnect() -> bool`

Like `reconnect` but uses the stored credentials and restores state:
`get_symbols()`, `init_trading()`, `subscribe_all()`. Called by the tick
listener when the socket fails.

## client.account

### `get_account_info() -> Optional[AccountInfo]`

### `init_trading() -> Optional[Frame]`

Opens the trading session. Its payload contains the open-position list, which
`get_positions()` decodes.

### `get_history(from_ts: int = 0, to_ts: int = 0) -> tuple[list[Deal], list[HistoryOrder]]`

Unix timestamps. `0, 0` asks for everything the server is willing to send.

## client.symbols

### `get_symbol_types() -> Optional[Frame]`

### `get_symbols() -> list[Symbol]`

Downloads and decompresses the symbol table and refreshes `symbol_list`,
`symbol_map`, `ta_to_sym`. Empty list on failure.

### `resolve_symbols(ta_list: list[int]) -> Optional[Frame]`

Requests per-symbol metadata. Must precede `subscribe` for new symbols.

### `subscribe(ta_values: int | list[int]) -> None`

Start the tick stream for the given symbol ids. Fire and forget.

### `subscribe_by_name(*names: str) -> None`

Resolve and subscribe by symbol name. Unknown names are ignored.

### `subscribe_all() -> tuple[int, bytes]`

Resolve and subscribe every symbol in one call. Returns
`(count, resolve_payload)`; the payload feeds the helpers below.

### Resolve-payload helpers

Partially decoded metadata, kept for research:

- `parse_trade_sessions(resolve_data) -> dict[int, list[tuple[int, int]]]`
- `parse_trade_modes(resolve_data) -> dict[int, int]`
- `find_resolve_bid_offset(resolve_data, sym_name, expected_price, digits, tolerance=0.02)`
- `extract_resolve_prices(resolve_data, bid_offset) -> dict[str, float]`

## client.market

### `get_candles(symbol, timeframe='H1', count=1000, from_ts=None, to_ts=None) -> list[Candle]`

| Parameter | Notes |
|-----------|-------|
| `timeframe` | Name from `TIMEFRAMES` (case-insensitive) or its numeric id. `ValueError` on unknown name. |
| `count` | Keep at most this many most-recent candles. `0`/`None` keeps all. |
| `from_ts`, `to_ts` | Unix seconds. `to_ts` defaults to now. `from_ts` defaults to `to_ts - max(7 days, 3 × count × timeframe)`. |

### `parse_tick(data: bytes, offset=0) -> Optional[Tick]`
### `parse_ticks(payload: bytes) -> list[Tick]`

Decode tick records using the current symbol table.

### `on_tick(callback: Callable[[Tick], None]) -> None`

Register a callback. Exceptions inside callbacks are swallowed.

### `start_tick_listener(symbols=None) -> threading.Thread`

Start a daemon thread that reads frames and dispatches ticks. On socket
errors it calls `auth.auto_reconnect()` and retries. `symbols` is accepted for
compatibility and unused; subscribe beforehand.

### `stop_tick_listener() -> None`

## client.trading

All helpers return `TradeAck | TradeResult | None`; see README "Return values".

### `trade(order_type, symbol, lots, price=0.0, sl=0.0, tp=0.0, comment="", position=0, position_by=0, exec_mode=EXEC_MARKET, filling_ea=FILLING_FOK, flags=FLAGS_XA, deviation=0, order=0) -> Optional[TradeAck]`

Raw trade request.

| Parameter | Constants | Notes |
|-----------|-----------|-------|
| `order_type` | `ORDER_BUY`, `ORDER_SELL`, `ORDER_BUY_LIMIT`, `ORDER_SELL_LIMIT`, `ORDER_BUY_STOP`, `ORDER_SELL_STOP`, `ORDER_BUY_STOP_LIMIT`, `ORDER_SELL_STOP_LIMIT`, `ORDER_CLOSE_BY` | |
| `exec_mode` | `EXEC_MARKET` (default), `TRADE_ACTION_PENDING`, `TRADE_ACTION_SLTP`, `TRADE_ACTION_MODIFY`, `TRADE_ACTION_REMOVE` | Action the server performs |
| `filling_ea` | `FILLING_FOK`, `FILLING_IOC`, `FILLING_RETURN` | Pending/modify use `FILLING_RETURN` |
| `flags` | `FLAGS_NONE`, `FLAGS_XA` | |
| `position` | | Ticket to close or modify |
| `order` | | Pending order ticket to modify or remove |
| `lots` | | Converted with `lots × 1e8` |

### `wait_trade_result(timeout=30) -> Optional[TradeResult]`

Read frames until a final execution report arrives. Transient codes
(10001 ON_THE_WAY, 10002 ACCEPTED, 10003 PROCESSED) are skipped.

### Market
- `buy(symbol, lots, sl=0.0, tp=0.0, comment="")`
- `sell(symbol, lots, sl=0.0, tp=0.0, comment="")`

### Pending
- `buy_limit(symbol, lots, price, sl=0.0, tp=0.0, comment="")`
- `sell_limit(symbol, lots, price, sl=0.0, tp=0.0, comment="")`
- `buy_stop(symbol, lots, price, sl=0.0, tp=0.0, comment="")`
- `sell_stop(symbol, lots, price, sl=0.0, tp=0.0, comment="")`

### Modify / cancel
- `modify_sl_tp(symbol, position_ticket, sl=0.0, tp=0.0)`
- `modify_pending(symbol, order_ticket, price, sl=0.0, tp=0.0)`
- `cancel_order(symbol, order_ticket)`

### Close
- `close_position(symbol, ticket, lots=None, pos_type='BUY')` — opens the opposite side against `ticket`. `lots` defaults to `0.01`; pass the position's volume to close fully.
- `close_by_order(symbol, order_ticket, lots, pos_type='BUY')`

## client.positions

### `get_positions() -> list[Position]`

Sends `init_trading` and decodes the position list from its payload.

### `close_all(symbol: str | None = None) -> tuple[int, int]`

Close every open position, or only `symbol`. Returns `(closed, total)`.

### `track_positions(duration=60, callback=None) -> dict[str, dict[str, float]]`

Read ticks for `duration` seconds; after each tick frame call
`callback(list[PositionPnL])` for positions with a known price. Returns the
last `{symbol: {'bid': ..., 'ask': ...}}` seen. P&L is
`(current − open) × volume × contract_size`, sign-flipped for sells.

## mt5direct.discovery

Server-name resolution. Network functions accept `timeout` and a
`fetch(url, timeout) -> str` override for testing.

### `list_servers(search=None) -> list[str]`

MT5 server names from MetaQuotes' directory, filtered by case-insensitive substring.
This is the "search company" step of the MT5 app.

### `resolve_server(name, registry=None) -> Endpoint`

Candidates from the registry (exact entry, then broker pattern, then generic
guesses) are verified in order by reading the `__terminal_params` announcement on
`https://host:port/terminal`; the first host announcing `name` wins. A verified
guess is written to the learned cache. Raises `ServerNotFound`.

### `discover_from_url(url) -> list[Endpoint]`

Fetch a broker page (a terminal page or a launcher that embeds/links one), collect
every `https://host[:port]/terminal` reference, verify each, remember each.

### `load_registry(remote=True) -> Registry`

Bundled `data/webterminals.json`, overlaid with the GitHub copy (cached 24 h in
`MT5DIRECT_CACHE_DIR`, default `~/.cache/mt5direct/`) and this machine's learned
entries. `MT5DIRECT_OFFLINE=1` or `remote=False` skips the network.

### `inspect_host(host, port=443) -> list[Endpoint]`

Servers announced by a web terminal host; empty if unreachable or not a terminal.

### `candidate_addresses(name, registry) -> list[str]`

Unverified `host[:port]` guesses, most likely first.

### `Registry`
| Field | Type |
|-------|------|
| `servers` | `dict[str, str]` — server name → `host[:port]` |
| `patterns` | `dict[str, dict]` — broker prefix → `{"host": "{code}.domain", "port": 443}` |

### `Endpoint`
| Field | Type |
|-------|------|
| `host` | `str` |
| `port` | `int` — default 443 |
| `server` | `str` |
| `broker` | `str` — company name from the terminal page |
| `build` | `int` — server build |
| `path` | `str` — always `/terminal` |
| `address` | property, `host` or `host:port` |

## Models

All are `@dataclass(frozen=True, slots=True)` in `mt5direct.models`.

### `Frame`
| Field | Type |
|-------|------|
| `cmd` | `int` |
| `status` | `int` — `0` means success |
| `payload` | `bytes` |

### `AccountInfo`
| Field | Type |
|-------|------|
| `balance` | `float` |
| `credit` | `float` |
| `currency` | `str` |
| `raw` | `Frame` |

### `Symbol`
| Field | Type |
|-------|------|
| `name` | `str` |
| `description` | `str` |
| `index` | `int` — position in the server table |
| `ta` | `int` — server symbol id |
| `digits` | `int` |
| `path` | `str` — e.g. `Forex\Majors` |

### `Tick`
| Field | Type |
|-------|------|
| `ta` | `int` |
| `symbol` | `str` — `#<ta>` if unknown |
| `digits` | `int` |
| `bid`, `ask` | `float` — scaled to price |
| `bid_raw`, `ask_raw` | `float` — as sent |
| `last` | `float` |
| `timestamp` | `int` |
| `flags` | `int` |
| `spread` | `int` |

### `Candle`
| Field | Type |
|-------|------|
| `time` | `int` — unix seconds, bar open |
| `open`, `high`, `low`, `close` | `float` |
| `tick_volume` | `int` |
| `spread` | `int` |

### `Position`
| Field | Type |
|-------|------|
| `ticket` | `int` |
| `symbol` | `str` |
| `type` | `'BUY'` or `'SELL'` |
| `volume` | `float` lots |
| `price_open`, `price_current` | `float` |
| `sl`, `tp` | `float` — `0.0` if unset |
| `contract_size` | `float` |

### `PositionPnL`
| Field | Type |
|-------|------|
| `position` | `Position` |
| `current_price` | `float` |
| `pnl` | `float` |

### `Deal`
| Field | Type |
|-------|------|
| `deal` | `int` |
| `symbol` | `str` |
| `time` | `int` |
| `action` | `'BUY'` or `'SELL'` |
| `entry` | `'IN'` or `'OUT'` |
| `price` | `float` |
| `volume` | `float` lots |
| `profit` | `float` |

### `HistoryOrder`
| Field | Type |
|-------|------|
| `order` | `int` |

### `TradeAck`
| Field | Type |
|-------|------|
| `retcode` | `int | None` — `0` means accepted for processing |
| `retcode_str` | `str | None` |
| `raw` | `Frame` |

### `TradeResult`
| Field | Type |
|-------|------|
| `retcode` | `int` |
| `retcode_str` | `str` |
| `deal` | `int` |
| `order` | `int` |
| `volume` | `float` lots |
| `volume_raw` | `int` |
| `price` | `float` |
| `bid`, `ask` | `float` |
| `comment` | `str` |

On failure only `retcode` and `retcode_str` are meaningful; the rest are zero / empty.

## Constants

Importable from `mt5direct` or `mt5direct.constants`.

| Group | Names |
|-------|-------|
| Commands | `CMD_HELLO CMD_ACCOUNT CMD_INIT_TRADING CMD_HISTORY CMD_SUBSCRIBE CMD_TICK CMD_SYMBOL_TYPES CMD_CANDLES CMD_TRADE CMD_RESOLVE CMD_TRADE_RESULT CMD_LOGIN CMD_SYMBOLS CMD_PING` |
| Order types | `ORDER_BUY ORDER_SELL ORDER_BUY_LIMIT ORDER_SELL_LIMIT ORDER_BUY_STOP ORDER_SELL_STOP ORDER_BUY_STOP_LIMIT ORDER_SELL_STOP_LIMIT ORDER_CLOSE_BY` |
| Actions | `EXEC_INSTANT_NOPX EXEC_INSTANT_PX EXEC_MARKET EXEC_EXCHANGE TRADE_ACTION_DEAL TRADE_ACTION_PENDING TRADE_ACTION_SLTP TRADE_ACTION_MODIFY TRADE_ACTION_REMOVE` |
| Filling / flags | `FILLING_FOK FILLING_IOC FILLING_RETURN FLAGS_NONE FLAGS_XA` |
| Return codes | `RETCODES` (dict), `RETCODE_DONE`, `RETCODE_DONE_PARTIAL`, `retcode_name(code)` |
| Timeframes | `TIMEFRAMES` (name → id), `TF_SECONDS` (id → seconds) |
| Network | `TRADE_HOSTS`, `INITIAL_KEY`, `WS_PORT`, `WS_PATH` |
