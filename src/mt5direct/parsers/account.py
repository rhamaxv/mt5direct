from typing import Optional

from ..models import AccountInfo, Frame
from ..protocol import BinaryReader
from ..protocol.layouts import ACCOUNT_MIN_SIZE


def parse_account(frame: Optional[Frame]) -> Optional[AccountInfo]:
    """``None`` unless the frame is a successful reply of at least 89 bytes."""
    if frame is None or frame.status != 0 or len(frame.payload) < ACCOUNT_MIN_SIZE:
        return None
    r = BinaryReader(frame.payload)
    return AccountInfo(
        balance=r.f64(9),
        credit=r.f64(17),
        currency=r.wchar(25, 64),
        raw=frame,
    )
