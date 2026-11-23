import struct

from mt5direct.parsers import parse_history
from mt5direct.protocol.layouts import DEAL_RECORD_SIZE, ORDER_RECORD_SIZE


def _deal():
    rec = bytearray(DEAL_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', 55)
    rec[8:16] = struct.pack('<q', 66)
    rec[80:84] = struct.pack('<I', 1700000000)
    rec[88:100] = "XAUUSD".encode("utf-16-le")
    rec[152:156] = struct.pack('<I', 1)
    rec[156:160] = struct.pack('<I', 1)
    rec[160:168] = struct.pack('<d', 2000.5)
    rec[168:176] = struct.pack('<d', -0.5)
    rec[176:184] = struct.pack('<d', -0.2)
    rec[184:192] = struct.pack('<d', -0.1)
    rec[192:200] = struct.pack('<Q', 2_000_000)
    rec[200:208] = struct.pack('<d', -3.25)
    rec[256:260] = "tp".encode("utf-16-le")
    rec[320:328] = struct.pack('<q', 99)
    return bytes(rec)


def _order():
    rec = bytearray(ORDER_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', 77)
    rec[80:84] = struct.pack('<I', 1700000500)
    rec[88:100] = "EURUSD".encode('utf-16-le')
    rec[108:116] = struct.pack('<d', 1.08)
    rec[116:124] = struct.pack('<d', 1e11)
    rec[152:156] = struct.pack('<I', 2)
    rec[156:160] = struct.pack('<I', 4)
    rec[160:168] = struct.pack('<d', 1.09)
    rec[192:200] = struct.pack('<Q', 1_000_000)
    rec[256:260] = "lo".encode("utf-16-le")
    return bytes(rec)


def test_history_extended():
    deals, orders = parse_history(struct.pack('<I', 1) + _deal() + struct.pack('<I', 1) + _order())
    d = deals[0]
    assert (d.order, d.commission, d.swap, d.fee, d.comment, d.magic) == (66, -0.5, -0.2, -0.1, "tp", 99)
    o = orders[0]
    assert (o.order, o.time, o.symbol) == (77, 1700000500, "EURUSD")
    assert (o.type, o.state, o.price, o.volume) == ("BUY_LIMIT", "FILLED", 1.09, 0.01)
    assert (o.sl, o.tp, o.comment) == (1.08, 0.0, "lo")
