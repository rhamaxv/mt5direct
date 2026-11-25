import struct

from mt5direct.services.auth import login_payload

HOST = "mt5trial6.exwebterm.com"
# device @196; 4+64+128+16+64+64+8+128 = 476 -> host len @476, host @480, login @736, token @744, um @904, tail @912


def test_login_payload_layout():
    dev = b'\x07' * 16
    pl = login_payload(414545497, "pw", b'', 0, dev, HOST)
    assert len(pl) == 920
    assert pl[4:8] == "pw".encode("utf-16-le")
    assert pl[196:212] == dev
    assert struct.unpack_from('<I', pl, 476)[0] == len(HOST)
    assert pl[480:480 + 2 * len(HOST)] == HOST.encode("utf-16-le")
    assert struct.unpack_from('<Q', pl, 736)[0] == 414545497
    assert pl[744:904] == b'\x00' * 160


def test_token_payload_carries_token_and_um():
    tok = bytes(range(160))
    pl = login_payload(1, "", tok, 99, b'\x00' * 16, "h")
    assert pl[4:68] == b'\x00' * 64
    assert pl[744:904] == tok
    assert struct.unpack_from('<Q', pl, 904)[0] == 99
