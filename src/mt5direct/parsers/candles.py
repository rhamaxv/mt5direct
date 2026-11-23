from ..models import Candle
from ..protocol import BinaryReader
from ..protocol.layouts import CANDLE_RECORD_SIZE


def parse_candles(payload: bytes) -> list[Candle]:
    r = BinaryReader(payload)
    candles = []
    off = 0
    while off + CANDLE_RECORD_SIZE <= len(payload):
        candles.append(Candle(
            time=r.i32(off),
            open=r.f64(off + 4),
            high=r.f64(off + 12),
            low=r.f64(off + 20),
            close=r.f64(off + 28),
            tick_volume=r.i64(off + 36),
            spread=r.i32(off + 44),
        ))
        off += CANDLE_RECORD_SIZE
    return candles
