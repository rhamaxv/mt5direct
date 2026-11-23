"""Wire framing.

Outbound: ``[u32 encrypted_len][u32 1][AES(inner)]`` where
inner = ``[2 random bytes][u16 cmd][payload]``.

Inbound: skip 8 outer bytes, decrypt, then ``[2 bytes][u16 cmd][u8 status][payload]``.
"""

import os
import struct

from ..models.frame import Frame
from .crypto import AesCipher

OUTER_HEADER_SIZE = 8


def encode_frame(cipher: AesCipher, cmd: int, payload: bytes = b'') -> bytes:
    header = bytes([os.urandom(1)[0], os.urandom(1)[0]]) + struct.pack('<H', cmd)
    encrypted = cipher.encrypt(header + payload)
    return struct.pack('<II', len(encrypted), 1) + encrypted


def decode_frame(cipher: AesCipher, data: bytes):
    """Decrypt an inbound message; ``None`` if it cannot be parsed."""
    pt = cipher.decrypt(bytes(data)[OUTER_HEADER_SIZE:])
    if pt is None or len(pt) < 5:
        return None
    return Frame(cmd=struct.unpack('<H', pt[2:4])[0], status=pt[4], payload=pt[5:])
