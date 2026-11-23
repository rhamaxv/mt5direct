import struct

from mt5direct.models import KIND_DEAL, KIND_ORDER, KIND_ORDER_HISTORY
from mt5direct.parsers import parse_trade_transactions
from mt5direct.protocol.layouts import DEAL_RECORD_SIZE, POSITION_RECORD_SIZE
from mt5direct.services.base import PositionBook

from .test_positions_extended import _position, order_record


def _hdr(kind, seq, flag):
    return struct.pack('<III', kind, seq, flag)


def _deal(deal=900, order=5000, position_id=5000, entry=0, price=1.1, sl=1.08, tp=1.12, profit=0.0):
    rec = bytearray(DEAL_RECORD_SIZE)
    rec[0:8] = struct.pack('<q', deal)
    rec[72:80] = struct.pack('<q', order)
    rec[80:84] = struct.pack('<I', 1700000000)
    rec[88:100] = "EURUSD".encode('utf-16-le')
    rec[156:160] = struct.pack('<I', entry)
    rec[160:168] = struct.pack('<d', price)
    rec[176:184] = struct.pack('<d', sl)
    rec[184:192] = struct.pack('<d', tp)
    rec[192:200] = struct.pack('<Q', 1_000_000)
    rec[200:208] = struct.pack('<d', profit)
    rec[248:256] = struct.pack('<q', position_id)
    rec[320:328] = struct.pack('<d', 100000.0)
    rec[328:332] = struct.pack('<I', 5)
    return bytes(rec)


def _pos(ticket=5000, volume_raw=1_000_000):
    rec = bytearray(_position(volume_raw=volume_raw))
    rec[0:8] = struct.pack('<q', ticket)
    return bytes(rec)


def _tail(balance):
    return struct.pack('<d', balance) + b'\x00' * 40


def test_order_events():
    payload = (_hdr(KIND_ORDER, 1, 2) + order_record(5000, "EURUSD", 0, 0.0, 1.1, 1_000_000, 0, 1, 2, 4, 5000, "c")
               + _hdr(KIND_ORDER_HISTORY, 2, 0) + order_record(5000, "EURUSD", 0, 0.0, 1.1, 1_000_000, 0, 1, 2, 4, 5000, "c"))
    evs = parse_trade_transactions(payload)
    assert [e.kind for e in evs] == [KIND_ORDER, KIND_ORDER_HISTORY]
    assert evs[0].order.state == "FILLED" and evs[0].order.volume_current == 0.0
    assert evs[0].deal is None and evs[0].position is None


def test_deal_event_with_position_and_balance():
    payload = _hdr(KIND_DEAL, 7, 0) + _deal() + _pos() + _tail(10002035.05)
    (e,) = parse_trade_transactions(payload, leverage=500)
    assert e.deal.deal == 900 and e.deal.sl == 1.08 and e.deal.tp == 1.12
    assert e.position.ticket == 5000 and e.position.volume == 0.01 and e.position.margin > 0
    assert e.position_removed is False and e.balance == 10002035.05


def test_position_update_without_deal_and_removal():
    update = _hdr(KIND_DEAL, 8, 1) + b'\x00' * DEAL_RECORD_SIZE + _pos() + b'\x00' * 48
    (e,) = parse_trade_transactions(update)
    assert e.deal is None and e.position.ticket == 5000 and e.balance is None
    closed = _hdr(KIND_DEAL, 9, 0) + _deal(entry=1, profit=-0.06) + _pos(volume_raw=0) + _tail(10002034.99)
    (e2,) = parse_trade_transactions(closed)
    assert e2.position_removed and e2.deal.entry == "OUT"


def test_truncated_payload_stops_cleanly():
    payload = _hdr(KIND_DEAL, 1, 0) + _deal() + _pos()[:100]
    assert parse_trade_transactions(payload) == []


def test_position_book_follows_events():
    book = PositionBook()
    book.seed([], [])
    # pending order placed, then canceled
    placed = order_record(7000, "EURUSD", 2, 1.05, 1.10, 1_000_000, 1_000_000, 1, 0, 1, 0, "lim")
    for e in parse_trade_transactions(_hdr(KIND_ORDER, 1, 0) + placed):
        book.apply(e)
    assert 7000 in book.pending and book.pending[7000].type == "BUY_LIMIT"
    canceled = order_record(7000, "EURUSD", 2, 1.05, 1.10, 1_000_000, 1_000_000, 1, 2, 2, 0, "lim")
    for e in parse_trade_transactions(_hdr(KIND_ORDER, 2, 0) + canceled):
        book.apply(e)
    assert 7000 not in book.pending
    # position opened, modified, closed
    for e in parse_trade_transactions(_hdr(KIND_DEAL, 3, 0) + _deal() + _pos() + _tail(100.0)):
        book.apply(e)
    assert list(book.positions) == [5000] and book.balance == 100.0
    for e in parse_trade_transactions(_hdr(KIND_DEAL, 4, 0) + _deal(entry=1) + _pos(volume_raw=0) + _tail(99.0)):
        book.apply(e)
    assert book.positions == {} and book.balance == 99.0
