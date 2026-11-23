import struct

from mt5direct.parsers import parse_history
from mt5direct.protocol.layouts import DEAL_RECORD_SIZE

from .test_positions_extended import order_record


def _deal(deal=55, order=66, symbol="XAUUSD", t=1700000000, action=1, entry=1, price=2000.5, price_position=1990.0,
          vol_raw=2_000_000, profit=-3.25, position_id=5000, comment="tp", contract=100.0, digits=2):
    rec = bytearray(DEAL_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', deal)
    rec[72:80] = struct.pack('<q', order)
    rec[80:84] = struct.pack('<I', t)
    rec[88:88 + len(symbol) * 2] = symbol.encode('utf-16-le')
    rec[152:156] = struct.pack('<I', action)
    rec[156:160] = struct.pack('<I', entry)
    rec[160:168] = struct.pack('<d', price)
    rec[168:176] = struct.pack('<d', price_position)
    rec[192:200] = struct.pack('<Q', vol_raw)
    rec[200:208] = struct.pack('<d', profit)
    rec[208:216] = struct.pack('<d', 1.0)
    rec[248:256] = struct.pack('<q', position_id)
    rec[256:256 + len(comment) * 2] = comment.encode('utf-16-le')
    rec[320:328] = struct.pack('<d', contract)
    rec[328:332] = struct.pack('<I', digits)
    return bytes(rec)


def test_history_deal_and_order_layouts():
    order = order_record(77, "EURUSD", 2, 1.09, 1.10042, 1_000_000, 0, 1700000500, 1700000600, 4, 5000, "lo")
    deals, orders = parse_history(struct.pack('<I', 1) + _deal() + struct.pack('<I', 1) + order + b'\x00' * 12)
    d = deals[0]
    assert (d.deal, d.order, d.position_id) == (55, 66, 5000)
    assert (d.action, d.entry, d.price, d.price_position, d.volume, d.profit) == ("SELL", "OUT", 2000.5, 1990.0, 0.02, -3.25)
    assert (d.comment, d.contract_size, d.digits) == ("tp", 100.0, 2)
    o = orders[0]
    assert (o.order, o.symbol, o.type, o.state) == (77, "EURUSD", "BUY_LIMIT", "FILLED")
    assert (o.time_setup, o.time_done, o.price, o.price_current) == (1700000500, 1700000600, 1.09, 1.10042)
    assert (o.volume, o.volume_current, o.position_id, o.comment) == (0.01, 0.0, 5000, "lo")
    assert (o.contract_size, o.digits, o.type_filling) == (100000.0, 5, 2)


def test_history_short_payload():
    assert parse_history(b'\x01\x00') == ([], [])
