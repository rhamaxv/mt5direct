import struct

from mt5direct.parsers import parse_trade_result
from mt5direct.protocol.layouts import TRADE_RESULT_MIN_SIZE, TRADE_RESULT_OFFSET


def _result(rc):
    buf = bytearray(TRADE_RESULT_MIN_SIZE)
    buf[TRADE_RESULT_OFFSET:TRADE_RESULT_OFFSET + 4] = struct.pack('<I', rc)
    return bytes(buf)


def test_in_flight_is_skipped_by_default_but_available_for_events():
    assert parse_trade_result(_result(10002)) is None
    ev = parse_trade_result(_result(10002), include_in_flight=True)
    assert ev.retcode == 10002 and ev.in_flight and not ev.filled


def test_filled_flag():
    assert parse_trade_result(_result(10009)).filled
