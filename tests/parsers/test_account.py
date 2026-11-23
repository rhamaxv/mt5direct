import struct

from mt5direct.models import Frame
from mt5direct.parsers import parse_account


def _account_payload(balance, credit, currency):
    buf = bytearray(89)
    buf[9:17] = struct.pack('<d', balance)
    buf[17:25] = struct.pack('<d', credit)
    enc = currency.encode('utf-16-le')
    buf[25:25 + len(enc)] = enc
    return bytes(buf)


def test_parse_account_ok():
    a = parse_account(Frame(cmd=3, status=0, payload=_account_payload(1000.5, 0.0, 'USD')))
    assert a.balance == 1000.5 and a.credit == 0.0 and a.currency == 'USD'


def test_parse_account_error_status():
    assert parse_account(Frame(cmd=3, status=1, payload=_account_payload(1, 0, 'USD'))) is None


def test_parse_account_short():
    assert parse_account(Frame(cmd=3, status=0, payload=b'\x00' * 88)) is None


def test_parse_account_none():
    assert parse_account(None) is None
