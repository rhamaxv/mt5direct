# Wire protocol

What `mt5direct` sends and receives. Everything is little-endian. This was
recovered by observation and is complete enough for the features the library
exposes; fields marked *unknown* are passed through untouched.

## Transport

- `wss://<host>:443/terminal`, binary WebSocket frames.
- TLS certificates are verified by default. Every broker host seen so far presents a
  valid certificate (Sectigo, Let's Encrypt, Google Trust Services); pass
  `verify_ssl=False` to `MT5Client` for a broker that does not.

## Encryption

AES-256-CBC, IV = 16 zero bytes, PKCS#7 padding. One key per session:

1. Before the handshake, the client uses the bootstrap key
   `INITIAL_KEY` (`constants/network.py`).
2. The hello reply carries the session key at payload bytes `66..98`.
   Every later message in both directions uses that key.

Implementation: `protocol/crypto.py`.

## Framing

Outbound:

```
[u32 encrypted_len][u32 1][ AES( [u8 rnd][u8 rnd][u16 cmd][payload] ) ]
```

Inbound: skip the 8-byte outer header, decrypt, then

```
[u8 rnd][u8 rnd][u16 cmd][u8 status][payload]
```

`status == 0` is success. Implementation: `protocol/framing.py`, model
`models/frame.py` (`Frame(cmd, status, payload)`).

Replies are matched to requests by `cmd`. Frames that arrive while waiting for
a different `cmd` (ticks, trade events) are queued and surfaced by
`recv_any()`. Implementation: `transport/session.py`.

## Handshake

| Step | cmd | Payload | Reply |
|------|-----|---------|-------|
| Hello | 0 | 64 zero bytes | `u16 server_id` at 0, session key at 66..98 |

## Field serializer

Request payloads are built with `protocol/serializer.py`:

| Type | Encoding |
|------|----------|
| `UINT32` | `<I` |
| `INT64` | `<q` |
| `UINT64` | `<Q` |
| `FLOAT64` | `<d` |
| `WCHAR` | UTF-16-LE, truncated or zero-padded to `pad` bytes |
| `BUFFER` | raw bytes, zero-padded to `pad` |

Strings are therefore fixed-width: a 64-byte `WCHAR` holds 32 characters.

## Numeric conventions

| Value | Encoding |
|-------|----------|
| Volume | `lots × 1e8` as integer (`0.01` lot → `1_000_000`) |
| Order prices | plain `float64` |
| Tick prices | `float64` holding the price scaled by `10^digits`; the parser divides it back |
| Timestamps | unix seconds (`u32`/`i32`/`i64` depending on record) |

## Commands

| cmd | Name | Direction | Payload | Reply |
|-----|------|-----------|---------|-------|
| 0 | HELLO | → | 64 zero bytes | server id, session key |
| 28 | LOGIN | → | see below | status only |
| 3 | ACCOUNT | → | empty | account record |
| 4 | INIT_TRADING | → | empty | position + pending order snapshot at login time |
| 9 | SYMBOL_TYPES | → | empty | opaque |
| 34 | SYMBOLS | → | empty | zlib symbol table |
| 18 | RESOLVE | → | `u32 n, n × u32 ta` | 3068-byte record per symbol |
| 7 | SUBSCRIBE | → | `u32 n, n × u32 ta` | none |
| 8 | TICK | ← | 50-byte tick records | |
| 10 | TRADE_TRANSACTION | ← | trade events, see below | |
| 11 | CANDLES | → | `wchar[64] symbol, u16 tf, u32 from, u32 to` | 48-byte candle records |
| 12 | TRADE | → | trade request | `u32 retcode` |
| 19 | TRADE_RESULT | ← | execution report | |
| 5 | HISTORY | → | `u32 from, u32 to` | deals + orders |
| 51 | PING | → | empty | any |

### Login (28)

```
u32 0
wchar[64]  password
wchar[128] ""
buf[16]    sha1("Python;1;en-US;1920x1080;mt5standalone")[:16]   (device hash)
wchar[64]  ""
wchar[64]  ""
u64 0
wchar[128] ""
u32 0
wchar[256] ""
u64        login
buf[160]   zeros
u64 0
```

### Trade request (12)

Field order taken from the official web terminal's request builder:

```
u32 0                  request id
u32 action             EXEC_MARKET | TRADE_ACTION_*
wchar[64] symbol
u64 volume_raw
u32 digits             of the symbol
i64 order              pending ticket for modify/remove
u32 type               ORDER_*
u32 type_filling
u32 type_time
u32 flags
u32 0
f64 price
f64 price_trigger      stop-limit trigger price
f64 sl
f64 tp
u32 deviation
f64 0
f64 0
wchar[64] comment
u64 position           ticket to close/modify
u64 position_by
u32 expiration
```

Modify and remove requests must repeat the pending order's type, price and volume,
otherwise the server answers `ORDER_LOCKED` (10023).

Reply payload: `u32 retcode`. `0` means queued; the final outcome arrives as a
cmd 19 event.

### Candle request (11)

`wchar[64] symbol | u16 timeframe_id | u32 from_ts | u32 to_ts`. Timeframe ids
are MT5's: `M1..M30` = minutes, `H1` = `0x4001`, `D1` = `0x4018`,
`W1` = `0x8001`, `MN1` = `0xC001` (see `constants/timeframes.py`).

## Record layouts

Sizes and offsets live in `protocol/layouts.py`; decoders in `parsers/`.

### Account (cmd 3), ≥ 89 bytes

| Offset | Type | Field |
|--------|------|-------|
| 9 | f64 | balance |
| 17 | f64 | credit |
| 25 | wchar[64] | currency |
| 89 | u32 | account type (2 = demo) |
| 93 | u32 | leverage |
| 97 | wchar[256] | group |
| 353 | u16 | server id |
| 355 | wchar[128] | server name |
| 483 | wchar[128] | company |
| 752 | f64 | stop-out level |

Fields past 89 bytes are read only when the payload is long enough.

### Login reply (cmd 28)

Bytes 0..160: session token; bytes 160..168: a u64 the web terminal sends back as the
second-to-last field of its next login. Replaying both on a fresh connection was
rejected by the Exness server (`dd=10`) in testing, so token login is exposed but
unverified.

### Symbol table (cmd 34)

Payload: 4 unknown bytes, then zlib stream. Decompressed:
`u32 count`, then `count` records of equal size (`len / count`, ≥ 460).

| Offset | Type | Field |
|--------|------|-------|
| 0 | wchar[64] | name |
| 64 | wchar[128] | description |
| 192 | u32 | digits |
| 196 | u32 | ta (symbol id) |
| 200 | wchar[256] | path |

### Tick (cmd 8), 50 bytes each, concatenated

| Offset | Type | Field |
|--------|------|-------|
| 0 | u32 | ta |
| 4 | u32 | unknown |
| 8 | u32 | unknown |
| 12 | f64 | bid × 10^digits |
| 20 | f64 | ask × 10^digits |
| 28 | f64 | last |
| 36 | i64 | timestamp |
| 44 | u32 | flags |
| 48 | u16 | spread |

### Candle (cmd 11), 48 bytes each

| Offset | Type | Field |
|--------|------|-------|
| 0 | i32 | time |
| 4 | f64 | open |
| 12 | f64 | high |
| 20 | f64 | low |
| 28 | f64 | close |
| 36 | i64 | tick_volume |
| 44 | i32 | spread |

### Position (cmd 4 reply)

`u32 count`, then `count` × 344-byte records. Verified on live records (EURUSD, BTCUSD):

| Offset | Type | Field |
|--------|------|-------|
| 0 | i64 | ticket |
| 16 | u32 | time_open |
| 20 | u32 | time_update |
| 24 | wchar[64] | symbol |
| 88 | u32 | direction (0 buy, 1 sell) |
| 92 | f64 | price_open |
| 100 | f64 | price_current |
| 108 | f64 | sl |
| 116 | f64 | tp |
| 124 | u64 | volume_raw |
| 132 | f64 | profit |
| 140 | f64 | 1.0 on USD accounts (conversion rate, not decoded) |
| 148 | f64 | price_open again (not decoded) |
| 180 | i64 | ticket again |
| 188 | wchar[64] | comment |
| 252 | f64 | contract_size |
| 260 | u32 | digits |

`sl`/`tp` ≥ 1e10 are server placeholders and are reported as `0.0`. Swap and
commission were zero on every record seen, so their offsets are unknown and the
fields are not exposed.

### Orders (cmd 4 reply after the positions, and cmd 5 reply after the deals)

`u32 count`, then `count` × 356-byte records, possibly followed by a few trailing
bytes. Pending orders and history orders share this layout:

| Offset | Type | Field |
|--------|------|-------|
| 0 | i64 | ticket |
| 72 | wchar[64] | symbol |
| 136 | u32 | time_setup |
| 144 | u32 | time_done (0 while active) |
| 148 | u32 | type (`ORDER_TYPE_NAMES`) |
| 152 | u32 | type_filling |
| 164 | f64 | price (0 for market orders) |
| 180 | f64 | price_current (fill price for market orders) |
| 188 | f64 | sl |
| 196 | f64 | tp |
| 204 | u64 | volume_initial (raw) |
| 212 | u64 | volume_current (raw, 0 when filled) |
| 220 | u32 | state (`ORDER_STATE_NAMES`: 1 placed, 2 canceled, 4 filled) |
| 232 | i64 | position id |
| 240 | wchar[64] | comment |
| 304 | f64 | contract_size |
| 312 | u32 | digits |
| 336 | f64 | price again |

### Deal (cmd 5 reply), 356 bytes

| Offset | Type | Field |
|--------|------|-------|
| 0 | i64 | deal |
| 72 | i64 | order |
| 80 | u32 | time |
| 88 | wchar[64] | symbol |
| 152 | u32 | action (0 buy, 1 sell) |
| 156 | u32 | entry (0 in, 1 out) |
| 160 | f64 | price |
| 168 | f64 | price of the position (0 on entry deals) |
| 176 | f64 | sl |
| 184 | f64 | tp |
| 192 | u64 | volume_raw |
| 200 | f64 | profit |
| 208 | f64 | 1.0 (conversion rate, not decoded) |
| 216 | f64 | price again |
| 248 | i64 | position id |
| 256 | wchar[64] | comment |
| 320 | f64 | contract_size |
| 328 | u32 | digits |

Commission, swap and fee were zero on every record seen; offsets unknown.

### Trade transactions (cmd 10)

The position list from cmd 4 is a snapshot that does not change during the session.
Every later change arrives as a cmd 10 push, one or more events back to back, each
``[u32 kind][u32 seq][u32 flag]`` plus a record:

| kind | Record | Meaning |
|------|--------|---------|
| 0 | order (356 bytes) | an active order changed; `flag` 2 was seen when it filled |
| 1 | order (356 bytes) | the order was written to history |
| 2 | deal (356) + position (344) + account tail (48) | a deal happened (`flag` 0) or a position was modified (`flag` 1, deal record all zero) |

A position record with volume 0 means the position is closed. The account tail's
first f64 is the balance; the rest is not decoded.

The library keeps a position/pending-order book from these events
(`client.book`, `client.get_positions()`).

### Trade result (cmd 19), ≥ 380 bytes

Base offset 252:

| +Offset | Type | Field |
|---------|------|-------|
| 0 | u32 | retcode |
| 4 | i64 | deal |
| 12 | i64 | order |
| 20 | i64 | volume_raw |
| 28 | f64 | price |
| 40 | f64 | bid |
| 48 | f64 | ask |
| 64 | wchar[64] | comment |

Codes 10001/10002/10003 are progress notifications and are skipped by
`wait_trade_result`.

### Resolve (cmd 18), 3068 bytes per symbol after a 4-byte header

Decoded regions:

| Offset | Type | Field |
|--------|------|-------|
| 1456 | f64 | contract size |
| 1800 | u32 | trade mode (`TRADE_MODE_NAMES`) |
| 1872 | u64 | volume min (raw) |
| 1880 | u64 | volume max (raw) |
| 1888 | u64 | volume step (raw) |
| 2164 + 64·day | u16, u16 | session start/end minutes, 7 days |

`tick_size = 10^-digits` and `tick_value = contract_size × tick_size` are derived.

`parsers/resolve.py` also carries probe helpers used to locate other fields.
