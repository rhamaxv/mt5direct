from ..models import Deal, HistoryOrder
from ..protocol import BinaryReader, raw_to_vol
from ..protocol.layouts import DEAL_RECORD_SIZE
from .orders import parse_order_records, to_history_order


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
            order=rec.i64(72),
            symbol=rec.wchar(88, 64),
            time=rec.u32(80),
            action='BUY' if rec.u32(152) == 0 else 'SELL',
            entry='IN' if rec.u32(156) == 0 else 'OUT',
            price=rec.f64(160),
            price_position=rec.f64(168),
            volume=raw_to_vol(rec.u64(192)),
            profit=rec.f64(200),
            position_id=rec.i64(248),
            comment=rec.wchar(256, 64),
            contract_size=rec.f64(320),
            digits=rec.u32(328),
        ))
        off += DEAL_RECORD_SIZE
    orders = []
    if off + 4 <= len(payload):
        orders = [to_history_order(f) for f in parse_order_records(payload[off + 4:], r.u32(off))]
    return deals, orders
