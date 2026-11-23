from mt5direct.protocol.serializer import (
    BUFFER, UINT32, WCHAR, raw_to_vol, serialize, vol_to_raw,
)
from mt5direct.protocol.reader import BinaryReader, read_wchar


def test_serialize_mixed_fields():
    out = serialize([[UINT32, 1], [WCHAR, 'ab', 8], [BUFFER, b'\x01', 4]])
    assert out == b'\x01\x00\x00\x00' b'a\x00b\x00\x00\x00\x00\x00' b'\x01\x00\x00\x00'


def test_serialize_wchar_truncates_to_pad():
    assert serialize([[WCHAR, 'abcdef', 4]]) == b'a\x00b\x00'


def test_serialize_empty_wchar_is_zero_filled():
    assert serialize([[WCHAR, '', 6]]) == b'\x00' * 6


def test_read_wchar_strips_nulls():
    assert read_wchar(b'a\x00b\x00\x00\x00', 0, 6) == 'ab'


def test_read_wchar_out_of_range_returns_empty():
    assert read_wchar(b'a\x00', 0, 6) == ''


def test_volume_roundtrip():
    assert vol_to_raw(0.01) == 1_000_000
    assert raw_to_vol(1_000_000) == 0.01


def test_binary_reader():
    r = BinaryReader(b'\x01\x00\x00\x00' + b'\x00\x00\x00\x00\x00\x00\xf0\x3f' + b'\x02\x00')
    assert r.u32(0) == 1
    assert r.f64(4) == 1.0
    assert r.u16(12) == 2
