import struct
import zlib

from mt5direct.parsers import parse_symbols

REC = 460


def _symbol_rec(name, desc, digits, ta, path):
    rec = bytearray(REC)
    rec[0:len(name) * 2] = name.encode('utf-16-le')
    rec[64:64 + len(desc) * 2] = desc.encode('utf-16-le')
    rec[192:196] = struct.pack('<I', digits)
    rec[196:200] = struct.pack('<I', ta)
    rec[200:200 + len(path) * 2] = path.encode('utf-16-le')
    return bytes(rec)


def test_parse_symbols_skips_blank_names():
    body = struct.pack('<I', 3) + _symbol_rec('EURUSD', 'Euro', 5, 7, 'Forex\\Majors') \
        + _symbol_rec('', '', 0, 0, '') + _symbol_rec('XAUUSD', 'Gold', 2, 9, 'Metals')
    payload = b'\x00' * 4 + zlib.compress(body)
    syms = parse_symbols(payload)
    assert [s.name for s in syms] == ['EURUSD', 'XAUUSD']
    assert syms[0].description == 'Euro' and syms[0].digits == 5 and syms[0].ta == 7
    assert syms[0].path == 'Forex\\Majors' and syms[0].index == 0
    assert syms[1].index == 2
