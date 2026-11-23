import struct

from mt5direct.models import Symbol
from mt5direct.parsers import parse_symbol_info, parse_symbol_infos
from mt5direct.protocol.layouts import RESOLVE_RECORD_SIZE

EURUSD = Symbol(name="EURUSD", description="Euro vs US Dollar", index=0, ta=7, digits=5, path="Forex")
XAUUSD = Symbol(name="XAUUSD", description="Gold", index=1, ta=9, digits=2, path="Metals")


def _record(trade_mode=4, contract_size=100000.0, vmin=1_000_000, vmax=20_000_000_000, vstep=1_000_000):
    rec = bytearray(RESOLVE_RECORD_SIZE)
    rec[1456:1464] = struct.pack('<d', contract_size)
    rec[1800:1804] = struct.pack('<I', trade_mode)
    rec[1872:1880] = struct.pack('<Q', vmin)
    rec[1880:1888] = struct.pack('<Q', vmax)
    rec[1888:1896] = struct.pack('<Q', vstep)
    return bytes(rec)


def test_parse_symbol_info():
    info = parse_symbol_info(_record(), EURUSD)
    assert info.trade_mode == "FULL" and info.trade_mode_id == 4
    assert info.contract_size == 100000.0
    assert info.tick_size == 1e-05 and info.tick_value == 100000.0 * 1e-05
    assert (info.volume_min, info.volume_max, info.volume_step) == (0.01, 200.0, 0.01)
    assert info.description == "Euro vs US Dollar" and info.path == "Forex"


def test_parse_symbol_info_short_record():
    assert parse_symbol_info(b'\x00' * 100, EURUSD) is None


def test_parse_symbol_infos_in_request_order():
    payload = b'\x00' * 4 + _record() + _record(trade_mode=3, contract_size=100.0)
    infos = parse_symbol_infos(payload, [EURUSD, XAUUSD])
    assert list(infos) == ["EURUSD", "XAUUSD"]
    assert infos["XAUUSD"].trade_mode == "CLOSEONLY" and infos["XAUUSD"].tick_size == 0.01
