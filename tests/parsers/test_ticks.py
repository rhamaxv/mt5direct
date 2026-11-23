import struct

from mt5direct.models import Symbol
from mt5direct.parsers import parse_tick, parse_ticks
from mt5direct.protocol.layouts import TICK_RECORD_SIZE

EURUSD = Symbol(name='EURUSD', description='', index=0, ta=7, digits=5, path='')


def _tick_bytes(ta=7, bid=123456.0, ask=123466.0, ts=1700000000, flags=2, spread=10):
    rec = struct.pack('<IIIdddqIH', ta, 0, 0, bid, ask, 0.0, ts, flags, spread)
    return rec.ljust(TICK_RECORD_SIZE, b'\x00')


def test_parse_tick_scales_by_symbol_digits():
    t = parse_tick(_tick_bytes(), 0, {7: EURUSD})
    assert t.symbol == 'EURUSD'
    assert t.bid == 1.23456
    assert t.ask == 1.23466
    assert t.bid_raw == 123456.0
    assert t.timestamp == 1700000000
    assert t.flags == 2
    assert t.spread == 10


def test_parse_tick_unknown_ta_falls_back():
    t = parse_tick(_tick_bytes(ta=99), 0, {})
    assert t.symbol == '#99'
    assert t.digits == 5


def test_parse_tick_past_end_returns_none():
    assert parse_tick(_tick_bytes()[:-1], 0, {}) is None


def test_parse_ticks_ignores_trailing_bytes():
    payload = _tick_bytes() + _tick_bytes(ta=8) + b'\x00' * 7
    ticks = parse_ticks(payload, {7: EURUSD})
    assert [t.ta for t in ticks] == [7, 8]
