# mt5direct: Refactor ke Library

Tanggal: 2026-11-23

## Tujuan

Mengubah `main.py` (satu file, 1005 baris, kelas `MT5Client` + `main()` demo) menjadi
package Python yang bisa di-`pip install`, berlapis, dan mudah dipakai. **Logika
protokol tidak berubah**: nilai cmd, offset byte, ukuran record, timeout, urutan field
serialize, dan nama method publik dipertahankan persis.

## Yang berubah

| Sebelum | Sesudah |
|---|---|
| Return value `dict` | Dataclass bertipe (`frozen=True, slots=True`), nama field = key dict lama |
| `{'nm','dd','z'}` | `Frame(cmd, status, payload)` |
| Angka cmd literal (`12`, `19`, `8`) | `CMD_TRADE`, `CMD_TRADE_RESULT`, `CMD_TICK` di `constants/commands.py` |
| `ConnectionError(...)` | `ConnectionFailed`, `LoginFailed` (turunan `ConnectionError`) |
| `except:` | `except Exception:` |
| `sys.path.insert(... Windows ...)` | Dihapus, diganti dependensi di `pyproject.toml` |
| Kredensial hardcoded di `main()` | Env var `MT5_LOGIN`, `MT5_PASSWORD` di `examples/demo.py` |
| `MT5Client` memegang ws/aes/queue/lock | Semua pindah ke `transport.Session` |

## Struktur

```
src/mt5direct/
  __init__.py  client.py  exceptions.py
  constants/   commands.py orders.py retcodes.py timeframes.py network.py
  protocol/    crypto.py framing.py serializer.py reader.py layouts.py
  transport/   websocket.py session.py
  models/      frame.py account.py symbol.py tick.py candle.py position.py history.py trade.py
  parsers/     account.py symbols.py resolve.py ticks.py candles.py positions.py history.py trade.py
  services/    base.py auth.py account.py symbols.py market_data.py trading.py positions.py
examples/      demo.py stream_ticks.py place_order.py
tests/         protocol/  parsers/
```

Dependensi hanya ke bawah: `client -> services -> transport -> protocol`,
`services -> parsers -> protocol, models`. `models` dan `protocol` tidak mengimpor
lapisan atas.

## Model

```
Frame        cmd, status, payload
AccountInfo  balance, credit, currency, raw: Frame
Symbol       name, description, index, ta, digits, path
Tick         ta, symbol, digits, bid, ask, bid_raw, ask_raw, last, timestamp, flags, spread
Candle       time, open, high, low, close, tick_volume, spread
Position     ticket, symbol, type, volume, price_open, price_current, sl, tp, contract_size
PositionPnL  Position + current_price, pnl
Deal         deal, symbol, time, action, entry, price, volume, profit
HistoryOrder order
TradeAck     retcode, retcode_str, raw: Frame
TradeResult  retcode, retcode_str, deal, order, volume, volume_raw, price, bid, ask, comment
```

`TradeResult` gagal (retcode bukan 10009/10011) mengisi `deal=0, volume=0, price=0`,
field lain default. Method order mengembalikan `TradeAck | TradeResult | None`, sama
seperti sebelumnya.

## API publik

`MT5Client` mempertahankan semua method lama dan mendelegasikan ke service:
`client.auth`, `client.account`, `client.symbols`, `client.market`, `client.trading`,
`client.positions`. Pemakai boleh memanggil `client.buy(...)` atau
`client.trading.buy(...)`.

Fungsi eksperimen (`find_resolve_bid_offset`, `extract_resolve_prices`,
`parse_trade_sessions`, `parse_trade_modes`) dipertahankan di `parsers/resolve.py`
dan tetap diekspos lewat `MT5Client`.

## Error

- `connect`/`login` gagal melempar `ConnectionFailed`/`LoginFailed`.
- Method lain yang dulu mengembalikan `None`/`[]` saat timeout tetap begitu.

## Testing

- Unit test untuk `protocol/` dan `parsers/` dengan byte buatan, tanpa koneksi.
- `transport/` dan `services/` tidak diuji otomatis (butuh server).
- Verifikasi akhir: `examples/demo.py` dijalankan dengan env var dan alurnya sama
  dengan `main.py` lama.

## Docs

Docstring satu-dua baris, hanya untuk hal yang tidak jelas dari nama. README berisi
instalasi dan tiga contoh pemakaian.
