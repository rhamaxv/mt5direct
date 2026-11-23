import struct

from mt5direct.models import Frame
from mt5direct.protocol.crypto import AesCipher
from mt5direct.protocol.framing import decode_frame, encode_frame

KEY = bytes(range(32))


def test_encode_has_outer_header():
    c = AesCipher(KEY)
    wire = encode_frame(c, 12, b'\x00\x01')
    enc_len, one = struct.unpack('<II', wire[:8])
    assert one == 1
    assert enc_len == len(wire) - 8
    assert enc_len % 16 == 0


def test_roundtrip_frame():
    c = AesCipher(KEY)
    frame = decode_frame(c, encode_frame(c, 12, b'\x00\x01\x02'))
    assert frame == Frame(cmd=12, status=0, payload=b'\x01\x02')


def test_decode_short_payload_returns_none():
    c = AesCipher(KEY)
    wire = encode_frame(c, 12, b'')
    assert decode_frame(c, wire) is None


def test_decode_garbage_returns_none():
    c = AesCipher(KEY)
    assert decode_frame(c, b'\x00' * 8 + b'\x01' * 7) is None
