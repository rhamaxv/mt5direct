import struct

from mt5direct.parsers import parse_history
from mt5direct.protocol.layouts import DEAL_RECORD_SIZE, ORDER_RECORD_SIZE


def _deal(deal_id, symbol, t, action, entry, price, volume_raw, profit):
    rec = bytearray(DEAL_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', deal_id)
    rec[72:80] = struct.pack('<q', 66)
    rec[80:84] = struct.pack('<I', t)
    rec[88:88 + len(symbol) * 2] = symbol.encode('utf-16-le')
    rec[152:156] = struct.pack('<I', action)
    rec[156:160] = struct.pack('<I', entry)
    rec[160:168] = struct.pack('<d', price)
    rec[192:200] = struct.pack('<Q', volume_raw)
    rec[200:208] = struct.pack('<d', profit)
    return bytes(rec)


def _order(order_id):
    rec = bytearray(ORDER_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', order_id)
    return bytes(rec)


def test_parse_history_deals_and_orders():
    payload = (struct.pack('<I', 1) + _deal(55, 'XAUUSD', 1700000000, 1, 1, 2000.5, 2_000_000, -3.25)
               + struct.pack('<I', 1) + _order(77))
    deals, orders = parse_history(payload)
    assert len(deals) == 1 and len(orders) == 1
    d = deals[0]
    assert d.deal == 55 and d.symbol == 'XAUUSD' and d.time == 1700000000
    assert d.action == 'SELL' and d.entry == 'OUT'
    assert d.price == 2000.5 and d.volume == 0.02 and d.profit == -3.25
    assert orders[0].order == 77


def test_parse_history_short_payload():
    assert parse_history(b'\x01\x00') == ([], [])
