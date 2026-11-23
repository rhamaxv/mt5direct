from typing import Mapping, Optional

from ..models import Symbol, Tick
from ..protocol import BinaryReader
from ..protocol.layouts import TICK_RECORD_SIZE

_DEFAULT_DIGITS = 5


def parse_tick(data: bytes, offset: int, ta_lookup: Mapping[int, Symbol]) -> Optional[Tick]:
    """Decode one 50-byte tick record. Unknown ``ta`` yields ``symbol='#<ta>'`` with 5 digits."""
    if offset + TICK_RECORD_SIZE > len(data):
        return None
    r = BinaryReader(data)
    o = offset
    ta = r.u32(o)
    o += 4 + 4 + 4
    bid = r.f64(o); o += 8
    ask = r.f64(o); o += 8
    last = r.f64(o); o += 8
    ts = r.i64(o); o += 8
    flags = r.u32(o); o += 4
    spread = r.u16(o)
    sym = ta_lookup.get(ta)
    name = sym.name if sym else f'#{ta}'
    digits = sym.digits if sym else _DEFAULT_DIGITS
    scale = 10 ** digits
    return Tick(
        ta=ta, symbol=name, digits=digits,
        bid=bid / scale, ask=ask / scale,
        bid_raw=bid, ask_raw=ask,
        last=last, timestamp=ts, flags=flags, spread=spread,
    )


def parse_ticks(payload: bytes, ta_lookup: Mapping[int, Symbol]) -> list[Tick]:
    ticks = []
    off = 0
    while off + TICK_RECORD_SIZE <= len(payload):
        tick = parse_tick(payload, off, ta_lookup)
        if tick:
            ticks.append(tick)
        off += TICK_RECORD_SIZE
    return ticks
