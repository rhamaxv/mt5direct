# mt5direct Library Refactor Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pecah `main.py` menjadi package `mt5direct` berlapis yang bisa di-pip-install, dengan return value dataclass, tanpa mengubah logika protokol.

**Architecture:** Lapisan `protocol` (byte murni) → `transport` (WebSocket + AES + queue) → `services` (alur perintah per domain) → `client` (facade). `parsers` mengubah bytes menjadi `models` dan hanya bergantung pada `protocol`+`models`, sehingga bisa diuji offline.

**Tech Stack:** Python ≥3.10, pycryptodome, websocket-client, pytest. Build backend: setuptools, layout `src/`.

**Spec:** `docs/superpowers/specs/2026-11-23-mt5direct-library-design.md`

## Global Constraints

- Semua nilai cmd, offset byte, ukuran record, timeout, dan urutan field `serialize` disalin persis dari `main.py`. Baris sumber dirujuk di setiap task.
- Nama method publik `MT5Client` tidak berubah.
- Nama field dataclass = key dict lama.
- Dataclass: `@dataclass(frozen=True, slots=True)`.
- `except:` → `except Exception:`. Tidak ada perubahan lain pada alur kontrol.
- Docstring 1–2 baris, hanya jika nama tidak cukup jelas.
- Tidak ada import dari lapisan atas ke bawah (lihat spec).
- Project bukan git repo: langkah "commit" diganti "lanjut".

## Review Focus

1. `parse_tick` dengan `ta` yang tidak ada di tabel simbol → `symbol="#<ta>"`, `digits=5`. Test di Task 6.
2. `parse_candles` dengan payload yang panjangnya bukan kelipatan 48 → sisa byte diabaikan, tidak error. Test di Task 6.
3. `parse_positions` dengan `sl`/`tp` ≥ 1e10 (nilai sampah server) → 0.0. Test di Task 6.
4. `decode_frame` dengan ciphertext kosong atau bukan kelipatan 16 → `None`, bukan exception. Test di Task 3.
5. `parse_trade_result` dengan payload < 380 byte → `None` (dilewati), seperti loop lama. Test di Task 6.

---

### Task 1: Scaffold package + constants

**Files:**
- Create: `pyproject.toml`, `src/mt5direct/__init__.py` (kosong dulu), `src/mt5direct/exceptions.py`
- Create: `src/mt5direct/constants/{__init__,commands,orders,retcodes,timeframes,network}.py`

**Interfaces:**
- Produces: `CMD_HELLO=0, CMD_ACCOUNT=3, CMD_INIT_TRADING=4, CMD_HISTORY=5, CMD_SUBSCRIBE=7, CMD_TICK=8, CMD_SYMBOL_TYPES=9, CMD_CANDLES=11, CMD_TRADE=12, CMD_RESOLVE=18, CMD_TRADE_RESULT=19, CMD_LOGIN=28, CMD_SYMBOLS=34, CMD_PING=51`
- Produces: semua konstanta `main.py:20-96` dengan nama sama; `MT5Error(Exception)`, `ConnectionFailed(MT5Error, ConnectionError)`, `LoginFailed(MT5Error, ConnectionError)`.

- [ ] Tulis `pyproject.toml` (name `mt5direct`, version `0.1.0`, deps `pycryptodome>=3.19`, `websocket-client>=1.6`, optional `dev=[pytest]`, `[tool.setuptools.packages.find] where=["src"]`).
- [ ] Salin konstanta dari `main.py:20-96` ke modul masing-masing; `constants/__init__.py` re-export semua.
- [ ] `python -c "import sys; sys.path.insert(0,'src'); from mt5direct.constants import *; assert TIMEFRAMES['H1']==16385 and RETCODES[10009]=='DONE'"` → OK.

### Task 2: protocol/serializer + reader + layouts

**Files:**
- Create: `src/mt5direct/protocol/{__init__,serializer,reader,layouts}.py`
- Test: `tests/protocol/test_serializer.py`

**Interfaces:**
- Produces: `serialize(fields) -> bytes` (`main.py:99-118`), `read_wchar(data, offset, length) -> str` (`main.py:121-124`), `vol_to_raw`, `raw_to_vol` (`main.py:91-96`), tipe field `UINT32, FLOAT64, INT64, UINT64, WCHAR, BUFFER`.
- Produces: `BinaryReader(data)` dengan `u16(off)`, `u32(off)`, `i32(off)`, `i64(off)`, `u64(off)`, `f64(off)`, `wchar(off, length)` — pembungkus `struct.unpack` little-endian.
- Produces `layouts.py`: `TICK_RECORD_SIZE=50`, `CANDLE_RECORD_SIZE=48`, `POSITION_RECORD_SIZE=344`, `POSITION_HEADER_SIZE=4`, `DEAL_RECORD_SIZE=356`, `ORDER_RECORD_SIZE=356`, `RESOLVE_RECORD_SIZE=3068`, `RESOLVE_SESSION_OFFSET=2164`, `RESOLVE_DAY_BLOCK_SIZE=64`, `RESOLVE_TRADE_MODE_OFFSET=1800`, `TRADE_RESULT_MIN_SIZE=380`, `TRADE_RESULT_OFFSET=252`, `SYMBOL_RECORD_MIN_SIZE=460`, `ACCOUNT_MIN_SIZE=89`.

- [ ] Test: `serialize([[UINT32,1],[WCHAR,'ab',8],[BUFFER,b'\x01',4]]) == b'\x01\x00\x00\x00a\x00b\x00\x00\x00\x00\x00\x01\x00\x00\x00'`; `read_wchar(b'a\x00b\x00\x00\x00',0,6)=='ab'`; `vol_to_raw(0.01)==1_000_000`; `raw_to_vol(1_000_000)==0.01`; `BinaryReader(b'\x01\x00\x00\x00').u32(0)==1`.
- [ ] Jalankan → FAIL (modul belum ada). Implementasi. Jalankan → PASS.

### Task 3: protocol/crypto + framing, models/frame

**Files:**
- Create: `src/mt5direct/protocol/crypto.py`, `src/mt5direct/protocol/framing.py`, `src/mt5direct/models/frame.py`
- Test: `tests/protocol/test_crypto.py`, `tests/protocol/test_framing.py`

**Interfaces:**
- Produces: `AesCipher(key).encrypt(plaintext) -> bytes` (`main.py:145-148`), `.decrypt(ciphertext) -> bytes | None` (`main.py:150-157`).
- Produces: `encode_frame(cipher, cmd, payload) -> bytes` (`main.py:159-162`: header 2 byte random + u16 cmd, encrypt, prefix `<II len 1`).
- Produces: `decode_frame(cipher, data) -> Frame | None` (`main.py:164-170`: skip 8 byte, decrypt, butuh ≥5 byte, `Frame(cmd=u16 @2, status=byte @4, payload=[5:])`).
- Produces: `Frame(cmd: int, status: int, payload: bytes)`.

- [ ] Test crypto: roundtrip `decrypt(encrypt(b'hello'))==b'hello'`; `decrypt(b'')` dan `decrypt(b'x'*15)` → `None`; IV nol: `encrypt(b'')` sama dengan `AES.new(key,MODE_CBC,b'\0'*16).encrypt(b'\x10'*16)`.
- [ ] Test framing: `decode_frame(c, encode_frame(c, 12, b'\xaa'))` → `Frame(12, 0xaa, b'')`... (status = byte pertama payload, jadi gunakan payload `b'\x00\x01\x02'` → `Frame(cmd=12, status=0, payload=b'\x01\x02')`).
- [ ] FAIL → implementasi → PASS.

### Task 4: models

**Files:**
- Create: `src/mt5direct/models/{__init__,account,symbol,tick,candle,position,history,trade}.py`

**Interfaces:** field persis seperti spec bagian "Model". `PositionPnL` punya field `position: Position, current_price: float, pnl: float`. `TradeResult` default `deal=0, order=0, volume=0.0, volume_raw=0, price=0.0, bid=0.0, ask=0.0, comment=""`.

- [ ] Tulis semua dataclass; `models/__init__.py` re-export.
- [ ] `python -c "...from mt5direct.models import *; Tick(ta=1,symbol='X',digits=5,bid=1.0,ask=1.0,bid_raw=1,ask_raw=1,last=0,timestamp=0,flags=0,spread=0)"` → OK.

### Task 5: transport (websocket + session)

**Files:**
- Create: `src/mt5direct/transport/{__init__,websocket,session}.py`

**Interfaces:**
- `WebSocketTransport(host, path='/terminal', port=443)` dengan `open(timeout=15)` (`main.py:186-187`), `send_binary(data)`, `recv(timeout) -> bytes` (settimeout + recv_data, kembalikan `bytes(data)`), `close()` (`main.py:838-842`).
- `Session(host)`: atribut `host`, `server_id`, `cipher`; method `connect()` (`main.py:185-193`, hello cmd 0 payload 64 nol, ambil `server_id=u16 @0`, key baru `payload[66:98]`; gagal → `ConnectionFailed`), `send(cmd, payload=b'')`, `recv(expected_cmd, timeout=15) -> Frame | None` (`main.py:172-189` dengan queue + lock), `recv_any(timeout=5) -> Frame | None` (`main.py:181-189`), `close()`, `is_open`.
- Perhatikan: `_recv_raw` lama membaca `pt[2:4]` sebagai cmd setelah skip 8 byte outer; `decode_frame` di Task 3 sudah mencakup ini.

- [ ] Implementasi. Tidak ada unit test (butuh server). Smoke: `python -c "from mt5direct.transport import Session"`.

### Task 6: parsers + tests

**Files:**
- Create: `src/mt5direct/parsers/{__init__,account,symbols,resolve,ticks,candles,positions,history,trade}.py`
- Test: `tests/parsers/test_{ticks,candles,positions,history,trade,account}.py`

**Interfaces (semua fungsi murni):**
- `parse_account(frame) -> AccountInfo | None` (`main.py:220-228`): butuh `status==0` dan `len>=89`; balance f64@9, credit f64@17, currency wchar@25 len 64. Jika tidak memenuhi → `None`.
- `parse_symbols(payload) -> list[Symbol]` (`main.py:238-264`): zlib decompress `payload[4:]`, count u32, rec_size = len//count, per record: name wchar@0/64, desc wchar@64/128, digits u32@192, ta u32@196, path wchar@200/256; skip jika `off+460>len`; skip jika name kosong.
- `parse_tick(data, offset, ta_lookup: Mapping[int, Symbol]) -> Tick | None` (`main.py:478-498`).
- `parse_ticks(payload, ta_lookup) -> list[Tick]`: loop step 50.
- `parse_candles(payload) -> list[Candle]` (`main.py:524-539`).
- `parse_positions(payload) -> list[Position]` (`main.py:686-720`).
- `parse_history(payload) -> tuple[list[Deal], list[HistoryOrder]]` (`main.py:582-626`).
- `parse_trade_ack(frame) -> TradeAck` (`main.py:420-424`): retcode u32@0 jika len≥4, else retcode=-1? **Tidak**: logika lama hanya menambah key jika len≥4; jadi `TradeAck(retcode=None, retcode_str=None, raw=frame)` saat len<4. Field `retcode: int | None`.
- `parse_trade_result(payload) -> TradeResult | None` (`main.py:426-460`): `None` jika len<380 atau rc di (10001,10002,10003); result penuh jika rc in (10009,10011); result gagal lainnya.
- `resolve.py`: `parse_trade_sessions(resolve_data, symbols)`, `parse_trade_modes(resolve_data, symbols)`, `find_resolve_bid_offset(resolve_data, symbols, sym_name, expected_price, digits, tolerance=0.02)`, `extract_resolve_prices(resolve_data, symbols, bid_offset)` (`main.py:290-382`, `self.symbols` → parameter).

- [ ] Test tick: bangun 50 byte dengan `struct.pack('<IIIdddqIH', ta=7, 0, 0, bid=123456.0, ask=123466.0, last=0, ts=1700000000, flags=2, spread=10)` + padding ke 50; lookup `{7: Symbol(name='EURUSD',digits=5,...)}` → `bid==1.23456`, `symbol=='EURUSD'`; lookup kosong → `symbol=='#7'`, `digits==5`. Offset melewati batas → `None`.
- [ ] Test candles: 2 record 48 byte + 5 byte sampah → 2 Candle, field tepat.
- [ ] Test positions: 1 record 344 byte dengan `sl=1e11` → `sl==0.0`; `direction=1` → `type=='SELL'`; volume_raw 1_000_000 → 0.01.
- [ ] Test history: 1 deal (356 byte) + count order 1 + 1 order (356 byte) → `(1 deal, 1 order)`; action=1 → 'SELL', entry=1 → 'OUT'.
- [ ] Test trade: payload 379 byte → `None`; 380 byte rc=10009 dengan deal/price → `TradeResult` lengkap; rc=10006 → `TradeResult(retcode=10006, retcode_str='REJECTED', deal=0,...)`; rc=10002 → `None`.
- [ ] Test account: payload 89 byte status 0 → balance/credit/currency tepat; status 1 → `None`.
- [ ] FAIL → implementasi → PASS.

### Task 7: services

**Files:**
- Create: `src/mt5direct/services/{__init__,base,auth,account,symbols,market_data,trading,positions}.py`

**Interfaces:**
- `BaseService(session: Session, state: ClientState)`; `ClientState` (di `services/base.py`) = objek mutable biasa: `symbols: list[Symbol]`, `symbol_map: dict[str, Symbol]`, `ta_to_sym: dict[int, Symbol]`, `login_id`, `password`.
- `AuthService.login(login_id, password) -> Frame` (`main.py:195-218`, gagal → `LoginFailed`), `ping()` (`main.py:829-831`), `reconnect(login_id=None, password=None) -> bool` (`main.py:833-845`), `auto_reconnect() -> bool` (`main.py:814-827`; memanggil symbols.get_symbols, account.init_trading, symbols.subscribe_all).
- `AccountService.get_account_info() -> AccountInfo | None`, `init_trading() -> Frame | None`, `get_history(from_ts=0, to_ts=0) -> tuple[list[Deal], list[HistoryOrder]]`.
- `SymbolService.get_symbol_types()`, `get_symbols() -> list[Symbol]` (isi state), `resolve_symbols(ta_list) -> Frame | None`, `subscribe(ta_values)`, `subscribe_by_name(*names)`, `subscribe_all() -> tuple[int, bytes]`, + wrapper `parse_trade_sessions/modes`, `find_resolve_bid_offset`, `extract_resolve_prices` yang meneruskan `state.symbols`.
- `MarketDataService.get_candles(symbol, timeframe='H1', count=1000, from_ts=None, to_ts=None) -> list[Candle]` (`main.py:500-542`), `parse_tick(data, offset=0)`, `on_tick(cb)`, `start_tick_listener(symbols=None) -> Thread`, `stop_tick_listener()` (`main.py:783-812`; pada exception panggil `auth.auto_reconnect`).
- `TradingService.trade(...) -> TradeAck | None` (signature persis `main.py:384-397`), `wait_trade_result(timeout=30) -> TradeResult | None`, `buy, sell, buy_limit, sell_limit, buy_stop, sell_stop, modify_sl_tp, modify_pending, cancel_order, close_position, close_by_order` dengan signature dan argumen `trade()` persis `main.py:462-473, 628-684`. Helper privat `_execute(ack)`: `if ack and ack.retcode == 0: return wait_trade_result(); return ack`.
- `PositionService.get_positions() -> list[Position]`, `close_all(symbol=None) -> tuple[int,int]` (`main.py:722-733`), `track_positions(duration=60, callback=None) -> dict` (`main.py:735-768`; callback menerima `list[PositionPnL]`).

- [ ] Implementasi semua service. Smoke import.

### Task 8: client facade + `__init__`

**Files:**
- Create: `src/mt5direct/client.py`; Modify: `src/mt5direct/__init__.py`

**Interfaces:**
- `MT5Client(host=None)`: atribut `session`, `auth`, `account`, `symbols`, `market`, `trading`, `positions`; properti `host`, `server_id`, `symbol_list` (= state.symbols), `symbol_map`, `ta_to_sym`. Semua method publik `main.py` ada sebagai delegasi satu baris. `connect()`, `close()`, `recv_any()`.
- Catatan nama: `client.symbols` adalah service, jadi daftar simbol lama (`client.symbols` list) tersedia sebagai `client.symbol_list`. Ini satu-satunya atribut yang berganti nama; dicatat di README.
- `__init__.py` ekspor: `MT5Client`, semua model, semua konstanta, exception, `__version__`.

- [ ] Implementasi. `python -c "from mt5direct import MT5Client, Tick, ORDER_BUY, TIMEFRAMES"` → OK.

### Task 9: examples + README + verifikasi

**Files:**
- Create: `examples/demo.py` (isi `main.py:848-1001`, pakai dataclass, kredensial dari `os.environ['MT5_LOGIN']`, `MT5_PASSWORD`), `examples/stream_ticks.py`, `examples/place_order.py`, `README.md`
- Delete: `main.py` → dipindah ke `legacy/main.py` agar bisa dibandingkan (tidak dihapus).

- [ ] `pip install -e '.[dev]'` di venv; `pytest` → semua PASS.
- [ ] `python -m compileall src examples` → OK.
- [ ] Jalankan `examples/demo.py` hanya jika env var tersedia; jika tidak, catat di laporan akhir bahwa verifikasi live belum dilakukan.
