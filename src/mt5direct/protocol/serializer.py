"""Field-list serializer for request payloads and lot/volume conversion."""

import struct

UINT32 = 6
FLOAT64 = 8
WCHAR = 11
BUFFER = 12
INT64 = 17
UINT64 = 18


def vol_to_raw(lots: float) -> int:
    """Lots to the server's fixed-point volume (1 lot = 1e8)."""
    return int(round(lots * 1e8))


def raw_to_vol(raw: int) -> float:
    return raw / 1e8


def serialize(fields) -> bytes:
    """Pack ``[type, value, pad?]`` entries into a little-endian byte string.

    WCHAR values are UTF-16-LE and truncated or zero-filled to ``pad`` bytes.
    BUFFER values are zero-filled up to ``pad`` bytes.
    """
    parts = []
    for f in fields:
        t, v = f[0], f[1] if len(f) > 1 else 0
        pad = f[2] if len(f) > 2 else None
        if t == UINT32:
            parts.append(struct.pack('<I', v))
        elif t == FLOAT64:
            parts.append(struct.pack('<d', v))
        elif t == INT64:
            parts.append(struct.pack('<q', v))
        elif t == UINT64:
            parts.append(struct.pack('<Q', v))
        elif t == WCHAR:
            enc = v.encode('utf-16-le') if v else b''
            if pad:
                enc = enc[:pad] + b'\x00' * max(0, pad - len(enc))
            parts.append(enc)
        elif t == BUFFER:
            d = v if isinstance(v, (bytes, bytearray)) else b''
            if pad and len(d) < pad:
                d = d + b'\x00' * (pad - len(d))
            parts.append(d)
    return b''.join(parts)
