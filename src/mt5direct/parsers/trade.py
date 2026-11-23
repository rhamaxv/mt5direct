from typing import Optional

from ..constants.retcodes import RETCODE_DONE, RETCODE_DONE_PARTIAL, retcode_name
from ..models import Frame, TradeAck, TradeResult
from ..protocol import BinaryReader, raw_to_vol
from ..protocol.layouts import TRADE_RESULT_MIN_SIZE, TRADE_RESULT_OFFSET

_IN_FLIGHT_CODES = (10001, 10002, 10003)


def parse_trade_ack(frame: Frame) -> TradeAck:
    if len(frame.payload) >= 4:
        code = BinaryReader(frame.payload).u32(0)
        return TradeAck(retcode=code, retcode_str=retcode_name(code), raw=frame)
    return TradeAck(retcode=None, retcode_str=None, raw=frame)


def parse_trade_result(payload: bytes) -> Optional[TradeResult]:
    """Decode a trade-result push. ``None`` while the order is still in flight or the frame is short."""
    if len(payload) < TRADE_RESULT_MIN_SIZE:
        return None
    r = BinaryReader(payload)
    off = TRADE_RESULT_OFFSET
    rc = r.u32(off)
    if rc in (RETCODE_DONE, RETCODE_DONE_PARTIAL):
        vol_exec = r.i64(off + 20)
        return TradeResult(
            retcode=rc,
            retcode_str=retcode_name(rc),
            deal=r.i64(off + 4),
            order=r.i64(off + 12),
            volume=raw_to_vol(vol_exec),
            volume_raw=vol_exec,
            price=r.f64(off + 28),
            bid=r.f64(off + 40),
            ask=r.f64(off + 48),
            comment=r.wchar(off + 64, 64),
        )
    if rc not in _IN_FLIGHT_CODES:
        return TradeResult(retcode=rc, retcode_str=retcode_name(rc))
    return None
