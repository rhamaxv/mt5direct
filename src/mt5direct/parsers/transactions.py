"""Trade transaction pushes (cmd 10).

Each event is a 12-byte header ``[u32 kind][u32 seq][u32 flag]`` followed by:

* kind 0 / 1: one 356-byte order record (active order changed / order moved to history);
* kind 2: a 356-byte deal record (all zero on pure position updates), a 344-byte
  position record (volume 0 when the position was closed) and a 48-byte account tail
  whose first f64 is the balance.

A payload may hold several events back to back.
"""

import struct

from ..models import KIND_DEAL, KIND_ORDER, KIND_ORDER_HISTORY, TradeTransaction
from ..protocol import BinaryReader
from ..protocol.layouts import DEAL_RECORD_SIZE, ORDER_RECORD_SIZE, POSITION_RECORD_SIZE
from .history import parse_deal_record
from .orders import parse_order_record, to_history_order
from .positions import parse_position_record

HEADER_SIZE = 12
ACCOUNT_TAIL_SIZE = 48


def parse_trade_transactions(payload: bytes, leverage: int = 0) -> list[TradeTransaction]:
    events = []
    off = 0
    while off + HEADER_SIZE <= len(payload):
        kind, seq, flag = struct.unpack_from('<III', payload, off)
        off += HEADER_SIZE
        if kind in (KIND_ORDER, KIND_ORDER_HISTORY):
            fields = parse_order_record(payload[off:off + ORDER_RECORD_SIZE])
            off += ORDER_RECORD_SIZE
            events.append(TradeTransaction(kind=kind, seq=seq, flag=flag,
                                           order=to_history_order(fields) if fields else None))
        elif kind == KIND_DEAL:
            deal_rec = payload[off:off + DEAL_RECORD_SIZE]
            off += DEAL_RECORD_SIZE
            pos_rec = payload[off:off + POSITION_RECORD_SIZE]
            off += POSITION_RECORD_SIZE
            tail = payload[off:off + ACCOUNT_TAIL_SIZE]
            off += ACCOUNT_TAIL_SIZE
            if len(pos_rec) < POSITION_RECORD_SIZE:
                break
            deal = parse_deal_record(deal_rec) if len(deal_rec) == DEAL_RECORD_SIZE and BinaryReader(deal_rec).i64(0) else None
            position = parse_position_record(pos_rec, leverage)
            removed = position is not None and position.volume == 0
            balance = struct.unpack_from('<d', tail, 0)[0] if len(tail) >= 8 and struct.unpack_from('<d', tail, 0)[0] else None
            events.append(TradeTransaction(kind=kind, seq=seq, flag=flag, deal=deal,
                                           position=position, position_removed=removed, balance=balance))
        else:
            break
    return events
