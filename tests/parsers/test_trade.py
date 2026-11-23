import struct

from mt5direct.models import Frame, TradeAck
from mt5direct.parsers import parse_trade_ack, parse_trade_result
from mt5direct.protocol.layouts import TRADE_RESULT_MIN_SIZE, TRADE_RESULT_OFFSET


def _result(rc, deal=0, order=0, vol=0, price=0.0, bid=0.0, ask=0.0, comment=''):
    buf = bytearray(TRADE_RESULT_MIN_SIZE)
    o = TRADE_RESULT_OFFSET
    buf[o:o + 4] = struct.pack('<I', rc)
    buf[o + 4:o + 12] = struct.pack('<q', deal)
    buf[o + 12:o + 20] = struct.pack('<q', order)
    buf[o + 20:o + 28] = struct.pack('<q', vol)
    buf[o + 28:o + 36] = struct.pack('<d', price)
    buf[o + 40:o + 48] = struct.pack('<d', bid)
    buf[o + 48:o + 56] = struct.pack('<d', ask)
    enc = comment.encode('utf-16-le')
    buf[o + 64:o + 64 + len(enc)] = enc
    return bytes(buf)


def test_trade_ack_with_code():
    ack = parse_trade_ack(Frame(cmd=12, status=0, payload=struct.pack('<I', 10009)))
    assert ack == TradeAck(retcode=10009, retcode_str='DONE', raw=ack.raw)


def test_trade_ack_without_code():
    ack = parse_trade_ack(Frame(cmd=12, status=0, payload=b'\x01'))
    assert ack.retcode is None and ack.retcode_str is None


def test_trade_result_short_payload_is_none():
    assert parse_trade_result(b'\x00' * (TRADE_RESULT_MIN_SIZE - 1)) is None


def test_trade_result_done():
    r = parse_trade_result(_result(10009, deal=5, order=6, vol=1_000_000, price=1.1, bid=1.09, ask=1.11, comment='ok'))
    assert r.retcode == 10009 and r.retcode_str == 'DONE'
    assert r.deal == 5 and r.order == 6
    assert r.volume == 0.01 and r.volume_raw == 1_000_000
    assert r.price == 1.1 and r.bid == 1.09 and r.ask == 1.11
    assert r.comment == 'ok'


def test_trade_result_rejected():
    r = parse_trade_result(_result(10006))
    assert r.retcode == 10006 and r.retcode_str == 'REJECTED'
    assert r.deal == 0 and r.volume == 0 and r.price == 0


def test_trade_result_in_flight_is_none():
    assert parse_trade_result(_result(10002)) is None
