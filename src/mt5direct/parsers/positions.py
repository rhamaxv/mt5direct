from ..models import Position
from ..protocol import BinaryReader, raw_to_vol
from ..protocol.layouts import POSITION_HEADER_SIZE, POSITION_RECORD_SIZE

_PRICE_SANITY_LIMIT = 1e10


def _clean_level(v: float) -> float:
    return v if 0 < v < _PRICE_SANITY_LIMIT else 0.0


def parse_positions(payload: bytes) -> list[Position]:
    """Decode the open-position list returned by the init-trading command."""
    if len(payload) < POSITION_HEADER_SIZE:
        return []
    r = BinaryReader(payload)
    pos_count = r.u32(0)
    positions = []
    for i in range(pos_count):
        base = POSITION_HEADER_SIZE + i * POSITION_RECORD_SIZE
        if base + POSITION_RECORD_SIZE > len(payload):
            break
        rec = BinaryReader(payload[base:base + POSITION_RECORD_SIZE])
        positions.append(Position(
            ticket=rec.i64(0),
            symbol=rec.wchar(24, 64),
            type='BUY' if rec.u32(88) == 0 else 'SELL',
            volume=raw_to_vol(rec.u64(124)),
            price_open=rec.f64(92),
            price_current=rec.f64(100),
            sl=_clean_level(rec.f64(108)),
            tp=_clean_level(rec.f64(116)),
            contract_size=rec.f64(248),
        ))
    return positions
