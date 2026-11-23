import struct

from mt5direct.parsers import parse_pending_orders, parse_positions
from mt5direct.protocol.layouts import POSITION_RECORD_SIZE


def _position(volume_raw=1_000_000, price_current=1.2, contract_size=100000.0, profit=3.5, swap=-0.1,
              commission=-0.7, time_open=1700000000, magic=42, comment="bot", digits=5):
    rec = bytearray(POSITION_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', 777)
    rec[16:20] = struct.pack('<I', time_open)
    rec[24:36] = "EURUSD".encode('utf-16-le')
    rec[88:92] = struct.pack('<I', 0)
    rec[92:100] = struct.pack('<d', 1.1)
    rec[100:108] = struct.pack('<d', price_current)
    rec[124:132] = struct.pack('<Q', volume_raw)
    rec[132:140] = struct.pack('<d', profit)
    rec[140:148] = struct.pack('<d', swap)
    rec[148:156] = struct.pack('<d', commission)
    rec[160:168] = struct.pack('<q', magic)
    rec[188:188 + len(comment) * 2] = comment.encode('utf-16-le')
    rec[248:256] = struct.pack('<d', contract_size)
    rec[260:264] = struct.pack('<I', digits)
    return bytes(rec)


def test_parse_positions_extended_fields_and_margin():
    (p,) = parse_positions(struct.pack('<I', 1) + _position(), leverage=500)
    assert (p.profit, p.swap, p.commission) == (3.5, -0.1, -0.7)
    assert (p.time_open, p.magic, p.comment, p.digits) == (1700000000, 42, "bot", 5)
    assert p.margin == 0.01 * 100000.0 * 1.2 / 500


def test_parse_positions_margin_zero_without_leverage():
    (p,) = parse_positions(struct.pack('<I', 1) + _position())
    assert p.margin == 0.0


def _pending(ticket, symbol, price, time_, comment, size=344):
    rec = bytearray(size)
    rec[0:8] = struct.pack('<q', ticket)
    rec[72:72 + len(symbol) * 2] = symbol.encode('utf-16-le')
    rec[136:140] = struct.pack('<I', time_)
    rec[240:240 + len(comment) * 2] = comment.encode('utf-16-le')
    rec[336:344] = struct.pack('<d', price)
    return bytes(rec)


def test_parse_pending_orders_after_positions():
    payload = (struct.pack('<I', 1) + _position()
               + struct.pack('<I', 2)
               + _pending(9001, "XAUUSD", 2000.5, 1700000100, "limit")
               + _pending(9002, "EURUSD", 1.05, 1700000200, ""))
    orders = parse_pending_orders(payload)
    assert [(o.ticket, o.symbol, o.price, o.time, o.comment) for o in orders] == [
        (9001, "XAUUSD", 2000.5, 1700000100, "limit"), (9002, "EURUSD", 1.05, 1700000200, "")]
    assert len(parse_positions(payload)) == 1


def test_parse_pending_orders_absent_or_garbage():
    assert parse_pending_orders(struct.pack('<I', 1) + _position()) == []
    assert parse_pending_orders(struct.pack('<I', 0) + struct.pack('<I', 50000) + b'\x00' * 400) == []
    assert parse_pending_orders(struct.pack('<I', 0) + struct.pack('<I', 1) + b'\x00' * 50) == []


def test_parse_pending_orders_sanity_checks():
    bad_time = _pending(9003, "GBPUSD", float('nan'), 5, "x")
    (o,) = parse_pending_orders(struct.pack('<I', 0) + struct.pack('<I', 1) + bad_time)
    assert o.time == 0 and o.price == 0.0 and o.symbol == "GBPUSD"
