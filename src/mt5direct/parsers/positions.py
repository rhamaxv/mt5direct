from typing import Optional

from ..models import PendingOrder, Position
from ..protocol import BinaryReader, raw_to_vol
from ..protocol.layouts import POSITION_HEADER_SIZE, POSITION_RECORD_SIZE
from .orders import parse_order_records, to_pending_order

_PRICE_SANITY_LIMIT = 1e10


def _clean_level(v: float) -> float:
    return v if 0 < v < _PRICE_SANITY_LIMIT else 0.0


def parse_position_record(rec_bytes: bytes, leverage: int = 0) -> Optional[Position]:
    """One 344-byte position record, or ``None`` if it has no ticket."""
    if len(rec_bytes) < POSITION_RECORD_SIZE:
        return None
    rec = BinaryReader(rec_bytes[:POSITION_RECORD_SIZE])
    ticket = rec.i64(0)
    if ticket <= 0:
        return None
    volume = raw_to_vol(rec.u64(124))
    price_current = rec.f64(100)
    contract_size = rec.f64(252)
    margin = 0.0
    if contract_size > 0 and leverage > 0:
        margin = volume * contract_size * price_current / leverage
    return Position(
        ticket=ticket,
        symbol=rec.wchar(24, 64),
        type='BUY' if rec.u32(88) == 0 else 'SELL',
        volume=volume,
        price_open=rec.f64(92),
        price_current=price_current,
        sl=_clean_level(rec.f64(108)),
        tp=_clean_level(rec.f64(116)),
        contract_size=contract_size,
        profit=rec.f64(132),
        time_open=rec.u32(16),
        comment=rec.wchar(188, 64),
        digits=rec.u32(260),
        margin=margin,
    )


def parse_positions(payload: bytes, leverage: int = 0) -> list[Position]:
    """Decode the open-position list at the start of the init-trading reply.

    ``margin`` is ``volume × contract_size × price_current / leverage`` when ``leverage`` is known.
    """
    if len(payload) < POSITION_HEADER_SIZE:
        return []
    r = BinaryReader(payload)
    pos_count = r.u32(0)
    positions = []
    for i in range(pos_count):
        base = POSITION_HEADER_SIZE + i * POSITION_RECORD_SIZE
        if base + POSITION_RECORD_SIZE > len(payload):
            break
        p = parse_position_record(payload[base:base + POSITION_RECORD_SIZE], leverage)
        if p:
            positions.append(p)
    return positions


def parse_pending_orders(payload: bytes) -> list[PendingOrder]:
    """Decode the pending-order block that follows the positions: ``u32 count`` + 356-byte records."""
    if len(payload) < POSITION_HEADER_SIZE:
        return []
    r = BinaryReader(payload)
    after = POSITION_HEADER_SIZE + r.u32(0) * POSITION_RECORD_SIZE
    if after + 4 > len(payload):
        return []
    count = r.u32(after)
    return [to_pending_order(f) for f in parse_order_records(payload[after + 4:], count)]
