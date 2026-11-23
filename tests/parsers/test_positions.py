import struct

from mt5direct.parsers import parse_positions
from mt5direct.protocol.layouts import POSITION_RECORD_SIZE


def _position(ticket, symbol, direction, price_open, price_current, sl, tp, volume_raw, contract_size):
    rec = bytearray(POSITION_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', ticket)
    rec[24:24 + len(symbol) * 2] = symbol.encode('utf-16-le')
    rec[88:92] = struct.pack('<I', direction)
    rec[92:100] = struct.pack('<d', price_open)
    rec[100:108] = struct.pack('<d', price_current)
    rec[108:116] = struct.pack('<d', sl)
    rec[116:124] = struct.pack('<d', tp)
    rec[124:132] = struct.pack('<Q', volume_raw)
    rec[248:256] = struct.pack('<d', contract_size)
    return bytes(rec)


def test_parse_positions_fields_and_sanity_filter():
    payload = struct.pack('<I', 1) + _position(
        123456789012, 'EURUSD', 1, 1.1, 1.2, 1e11, 1.3, 1_000_000, 100000.0)
    (p,) = parse_positions(payload)
    assert p.ticket == 123456789012
    assert p.symbol == 'EURUSD'
    assert p.type == 'SELL'
    assert p.volume == 0.01
    assert p.price_open == 1.1 and p.price_current == 1.2
    assert p.sl == 0.0
    assert p.tp == 1.3
    assert p.contract_size == 100000.0


def test_parse_positions_truncated_record_is_dropped():
    payload = struct.pack('<I', 2) + _position(1, 'X', 0, 1, 1, 0, 0, 0, 1) + b'\x00' * 10
    assert len(parse_positions(payload)) == 1


def test_parse_positions_short_payload():
    assert parse_positions(b'\x00') == []
