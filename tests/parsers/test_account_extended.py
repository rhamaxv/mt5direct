import struct

from mt5direct.models import Frame, Position
from mt5direct.parsers import parse_account, summarize_account


def _payload(balance=1000.0, credit=0.0, currency="USD", leverage=500, group="Pro",
             server="Exness-MT5Trial6", company="Exness Technologies Ltd", stopout=30.0):
    buf = bytearray(760)
    buf[9:17] = struct.pack('<d', balance)
    buf[17:25] = struct.pack('<d', credit)
    buf[25:25 + len(currency) * 2] = currency.encode('utf-16-le')
    buf[89:93] = struct.pack('<I', 2)
    buf[93:97] = struct.pack('<I', leverage)
    buf[97:97 + len(group) * 2] = group.encode('utf-16-le')
    buf[353:355] = struct.pack('<H', 6230)
    buf[355:355 + len(server) * 2] = server.encode('utf-16-le')
    buf[483:483 + len(company) * 2] = company.encode('utf-16-le')
    buf[752:760] = struct.pack('<d', stopout)
    return bytes(buf)


def test_parse_account_extended_fields():
    a = parse_account(Frame(cmd=3, status=0, payload=_payload()))
    assert (a.account_type, a.leverage, a.group) == (2, 500, "Pro")
    assert (a.server_id, a.server, a.company) == (6230, "Exness-MT5Trial6", "Exness Technologies Ltd")
    assert a.stopout_level == 30.0


def test_parse_account_short_payload_defaults():
    a = parse_account(Frame(cmd=3, status=0, payload=_payload()[:89]))
    assert a.balance == 1000.0 and a.leverage == 0 and a.server == ""


def _pos(profit, margin):
    return Position(ticket=1, symbol="EURUSD", type="BUY", volume=0.01, price_open=1.0,
                    price_current=1.0, sl=0, tp=0, contract_size=100000, profit=profit, margin=margin)


def test_summarize_account():
    a = parse_account(Frame(cmd=3, status=0, payload=_payload(balance=1000, credit=50)))
    s = summarize_account(a, [_pos(10.0, 20.0), _pos(-4.0, 30.0)])
    assert s.profit == 6.0 and s.margin == 50.0
    assert s.equity == 1056.0 and s.free_margin == 1006.0
    assert s.margin_level == 1056.0 / 50.0 * 100
    assert s.positions_count == 2


def test_summarize_account_no_margin():
    a = parse_account(Frame(cmd=3, status=0, payload=_payload()))
    s = summarize_account(a, [])
    assert s.margin_level == 0.0 and s.equity == 1000.0
