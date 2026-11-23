from ..models import PendingOrder, Position
from ..protocol import BinaryReader, raw_to_vol
from ..protocol.layouts import POSITION_HEADER_SIZE, POSITION_RECORD_SIZE

_PRICE_SANITY_LIMIT = 1e10
_PENDING_MIN_RECORD = 100
_PENDING_MAX_COUNT = 10000
_TIME_MIN, _TIME_MAX = 1577836800, 1893456000   # 2020-01-01 .. 2030-01-01


def _clean_level(v: float) -> float:
    return v if 0 < v < _PRICE_SANITY_LIMIT else 0.0


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
        rec = BinaryReader(payload[base:base + POSITION_RECORD_SIZE])
        volume = raw_to_vol(rec.u64(124))
        price_current = rec.f64(100)
        contract_size = rec.f64(248)
        margin = 0.0
        if contract_size > 0 and leverage > 0:
            margin = volume * contract_size * price_current / leverage
        positions.append(Position(
            ticket=rec.i64(0),
            symbol=rec.wchar(24, 64),
            type='BUY' if rec.u32(88) == 0 else 'SELL',
            volume=volume,
            price_open=rec.f64(92),
            price_current=price_current,
            sl=_clean_level(rec.f64(108)),
            tp=_clean_level(rec.f64(116)),
            contract_size=contract_size,
            profit=rec.f64(132),
            swap=rec.f64(140),
            commission=rec.f64(148),
            time_open=rec.u32(16),
            magic=rec.i64(160),
            comment=rec.wchar(188, 64),
            digits=rec.u32(260) if len(rec) >= 264 else 0,
            margin=margin,
        ))
    return positions


def parse_pending_orders(payload: bytes) -> list[PendingOrder]:
    """Decode the pending-order block that follows the positions in the init-trading reply.

    The record layout is only partially known, so the record size is derived from the
    count and every field is sanity-checked.
    """
    if len(payload) < POSITION_HEADER_SIZE:
        return []
    r = BinaryReader(payload)
    pos_count = r.u32(0)
    after = POSITION_HEADER_SIZE + pos_count * POSITION_RECORD_SIZE
    if after + 4 > len(payload):
        return []
    order_count = r.u32(after)
    if not 0 < order_count < _PENDING_MAX_COUNT:
        return []
    remaining = payload[after + 4:]
    if not remaining:
        return []
    rec_size = len(remaining) // order_count
    if rec_size < _PENDING_MIN_RECORD:
        return []
    orders = []
    for i in range(order_count):
        orec = BinaryReader(remaining[i * rec_size:(i + 1) * rec_size])
        if len(orec) < _PENDING_MIN_RECORD:
            break
        ticket = orec.i64(0)
        if ticket <= 0 or ticket > 1e15:
            continue
        symbol = orec.wchar(72, 64) if rec_size >= 136 else ''
        if not symbol or not symbol[0].isascii() or not symbol[0].isalpha():
            symbol = orec.wchar(24, 64)
        time_ = orec.u32(136) if rec_size >= 140 else 0
        if not (_TIME_MIN < time_ < _TIME_MAX):
            time_ = 0
        comment = orec.wchar(240, 64) if rec_size >= 304 else ''
        price = orec.f64(336) if rec_size >= 344 else 0.0
        if price != price or abs(price) > _PRICE_SANITY_LIMIT:
            price = 0.0
        orders.append(PendingOrder(ticket=ticket, symbol=symbol, price=price, time=time_, comment=comment))
    return orders
