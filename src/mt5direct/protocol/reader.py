"""Little-endian readers for response payloads."""

import struct


def read_wchar(data: bytes, offset: int, length: int) -> str:
    """Decode a fixed-width UTF-16-LE field; empty string if out of range."""
    end = offset + length
    if end > len(data):
        return ""
    return data[offset:end].decode('utf-16-le', errors='replace').rstrip('\x00')


class BinaryReader:
    """Offset-based accessors over a bytes object."""

    __slots__ = ('data',)

    def __init__(self, data: bytes):
        self.data = data

    def __len__(self) -> int:
        return len(self.data)

    def u16(self, off: int) -> int:
        return struct.unpack_from('<H', self.data, off)[0]

    def u32(self, off: int) -> int:
        return struct.unpack_from('<I', self.data, off)[0]

    def i32(self, off: int) -> int:
        return struct.unpack_from('<i', self.data, off)[0]

    def i64(self, off: int) -> int:
        return struct.unpack_from('<q', self.data, off)[0]

    def u64(self, off: int) -> int:
        return struct.unpack_from('<Q', self.data, off)[0]

    def f64(self, off: int) -> float:
        return struct.unpack_from('<d', self.data, off)[0]

    def wchar(self, off: int, length: int) -> str:
        return read_wchar(self.data, off, length)
