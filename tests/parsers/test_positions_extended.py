import struct

from mt5direct.parsers import parse_pending_orders, parse_positions
from mt5direct.protocol.layouts import ORDER_RECORD_SIZE, POSITION_RECORD_SIZE


def _position(volume_raw=1_000_000, price_current=1.2, contract_size=100000.0, profit=3.5,
              time_open=1700000000, comment="bot", digits=5):
    rec = bytearray(POSITION_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', 777)
    rec[16:20] = struct.pack('<I', time_open)
    rec[24:36] = "EURUSD".encode('utf-16-le')
    rec[88:92] = struct.pack('<I', 0)
    rec[92:100] = struct.pack('<d', 1.1)
    rec[100:108] = struct.pack('<d', price_current)
    rec[124:132] = struct.pack('<Q', volume_raw)
    rec[132:140] = struct.pack('<d', profit)
    rec[140:148] = struct.pack('<d', 1.0)            # rate, not decoded
    rec[148:156] = struct.pack('<d', 1.1)            # open price again, not decoded
    rec[188:188 + len(comment) * 2] = comment.encode('utf-16-le')
    rec[252:260] = struct.pack('<d', contract_size)
    rec[260:264] = struct.pack('<I', digits)
    return bytes(rec)


def test_parse_positions_extended_fields_and_margin():
    (p,) = parse_positions(struct.pack('<I', 1) + _position(), leverage=500)
    assert (p.profit, p.time_open, p.comment, p.digits) == (3.5, 1700000000, "bot", 5)
    assert p.contract_size == 100000.0
    assert p.margin == 0.01 * 100000.0 * 1.2 / 500


def test_parse_positions_margin_zero_without_leverage():
    (p,) = parse_positions(struct.pack('<I', 1) + _position())
    assert p.margin == 0.0


def order_record(ticket, symbol, type_id, price, price_current, vol_raw, vol_cur_raw, time_setup, time_done,
                 state_id, position_id, comment, filling=2, contract=100000.0, digits=5):
    rec = bytearray(ORDER_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', ticket)
    rec[72:72 + len(symbol) * 2] = symbol.encode('utf-16-le')
    rec[136:140] = struct.pack('<I', time_setup)
    rec[144:148] = struct.pack('<I', time_done)
    rec[148:152] = struct.pack('<I', type_id)
    rec[152:156] = struct.pack('<I', filling)
    rec[164:172] = struct.pack('<d', price)
    rec[180:188] = struct.pack('<d', price_current)
    rec[204:212] = struct.pack('<Q', vol_raw)
    rec[212:220] = struct.pack('<Q', vol_cur_raw)
    rec[220:224] = struct.pack('<I', state_id)
    rec[232:240] = struct.pack('<q', position_id)
    rec[240:240 + len(comment) * 2] = comment.encode('utf-16-le')
    rec[304:312] = struct.pack('<d', contract)
    rec[312:316] = struct.pack('<I', digits)
    return bytes(rec)


def test_parse_pending_orders_after_positions_with_trailing_bytes():
    payload = (struct.pack('<I', 1) + _position()
               + struct.pack('<I', 2)
               + order_record(9001, "XAUUSD", 2, 2000.5, 2050.0, 1_000_000, 1_000_000, 1700000100, 0, 1, 0, "limit", contract=100.0, digits=2)
               + order_record(9002, "EURUSD", 5, 1.05, 1.10, 2_000_000, 2_000_000, 1700000200, 0, 1, 0, "")
               + b'\x00' * 12)   # the server appends a few bytes after the records
    orders = parse_pending_orders(payload)
    assert [(o.ticket, o.symbol, o.type, o.price, o.volume, o.comment) for o in orders] == [
        (9001, "XAUUSD", "BUY_LIMIT", 2000.5, 0.01, "limit"), (9002, "EURUSD", "SELL_STOP", 1.05, 0.02, "")]
    assert orders[0].price_current == 2050.0 and orders[0].state == "PLACED"
    assert (orders[0].contract_size, orders[0].digits, orders[0].type_filling) == (100.0, 2, 2)
    assert len(parse_positions(payload)) == 1


def test_parse_pending_orders_absent_or_short():
    assert parse_pending_orders(struct.pack('<I', 1) + _position()) == []
    assert parse_pending_orders(struct.pack('<I', 0) + struct.pack('<I', 1) + b'\x00' * 50) == []
    assert parse_pending_orders(struct.pack('<I', 0) + struct.pack('<I', 1) + b'\x00' * ORDER_RECORD_SIZE) == []
