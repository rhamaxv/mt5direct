from ..constants.orders import ORDER_STATE_NAMES, ORDER_TYPE_NAMES
from ..models import Deal, HistoryOrder
from ..protocol import BinaryReader, raw_to_vol
from ..protocol.layouts import DEAL_RECORD_SIZE, ORDER_RECORD_SIZE

_PRICE_SANITY_LIMIT = 1e10


def _clean_level(v: float) -> float:
    return v if 0 < v < _PRICE_SANITY_LIMIT else 0.0


def parse_history(payload: bytes) -> tuple[list[Deal], list[HistoryOrder]]:
    """Decode ``[u32 deal_count][deals...][u32 order_count][orders...]``."""
    if len(payload) < 4:
        return [], []
    r = BinaryReader(payload)
    deal_count = r.u32(0)
    off = 4
    deals = []
    for _ in range(deal_count):
        if off + DEAL_RECORD_SIZE > len(payload):
            break
        rec = BinaryReader(payload[off:off + DEAL_RECORD_SIZE])
        deals.append(Deal(
            deal=rec.i64(0),
            order=rec.i64(8),
            symbol=rec.wchar(88, 64),
            time=rec.u32(80),
            action='BUY' if rec.u32(152) == 0 else 'SELL',
            entry='IN' if rec.u32(156) == 0 else 'OUT',
            price=rec.f64(160),
            commission=rec.f64(168),
            swap=rec.f64(176),
            fee=rec.f64(184),
            volume=raw_to_vol(rec.u64(192)),
            profit=rec.f64(200),
            comment=rec.wchar(256, 64),
            magic=rec.i64(320),
        ))
        off += DEAL_RECORD_SIZE
    orders = []
    if off + 4 <= len(payload):
        order_count = r.u32(off)
        off += 4
        for _ in range(order_count):
            if off + ORDER_RECORD_SIZE > len(payload):
                break
            rec = BinaryReader(payload[off:off + ORDER_RECORD_SIZE])
            o_type = rec.u32(152)
            o_state = rec.u32(156)
            orders.append(HistoryOrder(
                order=rec.i64(0),
                time=rec.u32(80),
                symbol=rec.wchar(88, 64),
                type=ORDER_TYPE_NAMES.get(o_type, f'TYPE_{o_type}'),
                state=ORDER_STATE_NAMES.get(o_state, f'STATE_{o_state}'),
                price=rec.f64(160),
                volume=raw_to_vol(rec.u64(192)),
                sl=_clean_level(rec.f64(108)),
                tp=_clean_level(rec.f64(116)),
                comment=rec.wchar(256, 64),
            ))
            off += ORDER_RECORD_SIZE
    return deals, orders
