"""356-byte order records, shared by the init-trading pending block and the history reply."""

from ..constants.orders import ORDER_STATE_NAMES, ORDER_TYPE_NAMES
from ..models import HistoryOrder, PendingOrder
from ..protocol import BinaryReader, raw_to_vol
from ..protocol.layouts import ORDER_RECORD_SIZE


def _order_fields(rec: BinaryReader) -> dict:
    type_id = rec.u32(148)
    state_id = rec.u32(220)
    return dict(
        symbol=rec.wchar(72, 64),
        type=ORDER_TYPE_NAMES.get(type_id, f'TYPE_{type_id}'),
        type_id=type_id,
        state=ORDER_STATE_NAMES.get(state_id, f'STATE_{state_id}'),
        state_id=state_id,
        time_setup=rec.u32(136),
        time_done=rec.u32(144),
        type_filling=rec.u32(152),
        price=rec.f64(164),
        price_current=rec.f64(180),
        volume=raw_to_vol(rec.u64(204)),
        volume_current=raw_to_vol(rec.u64(212)),
        position_id=rec.i64(232),
        comment=rec.wchar(240, 64),
        contract_size=rec.f64(304),
        digits=rec.u32(312),
    )


def parse_order_records(data: bytes, count: int) -> list[dict]:
    """``count`` consecutive 356-byte records from ``data``; trailing bytes are ignored."""
    out = []
    for i in range(count):
        off = i * ORDER_RECORD_SIZE
        if off + ORDER_RECORD_SIZE > len(data):
            break
        rec = BinaryReader(data[off:off + ORDER_RECORD_SIZE])
        ticket = rec.i64(0)
        if ticket <= 0:
            continue
        out.append(dict(ticket=ticket, **_order_fields(rec)))
    return out


def to_history_order(f: dict) -> HistoryOrder:
    f = dict(f)
    return HistoryOrder(order=f.pop('ticket'), **f)


def to_pending_order(f: dict) -> PendingOrder:
    return PendingOrder(
        ticket=f['ticket'], symbol=f['symbol'], type=f['type'], type_id=f['type_id'],
        price=f['price'], price_current=f['price_current'], volume=f['volume'],
        volume_current=f['volume_current'], time_setup=f['time_setup'], comment=f['comment'],
        state=f['state'], type_filling=f['type_filling'], contract_size=f['contract_size'],
        digits=f['digits'],
    )
