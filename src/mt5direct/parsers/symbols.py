import struct
import zlib

from ..models import Symbol
from ..protocol import BinaryReader
from ..protocol.layouts import SYMBOL_RECORD_MIN_SIZE


def parse_symbols(payload: bytes) -> list[Symbol]:
    """Decode the zlib-compressed symbol table. Record size is derived from the count."""
    data = zlib.decompress(payload[4:])
    sym_count = struct.unpack('<I', data[:4])[0]
    rec_data = data[4:]
    rec_size = len(rec_data) // sym_count if sym_count > 0 else 0
    r = BinaryReader(rec_data)
    symbols = []
    for i in range(sym_count):
        off = i * rec_size
        if off + SYMBOL_RECORD_MIN_SIZE > len(rec_data):
            break
        name = r.wchar(off, 64)
        if not name:
            continue
        symbols.append(Symbol(
            name=name,
            description=r.wchar(off + 64, 128),
            index=i,
            ta=r.u32(off + 196),
            digits=r.u32(off + 192),
            path=r.wchar(off + 200, 256),
        ))
    return symbols
