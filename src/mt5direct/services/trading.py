import time
from typing import Optional, Union

from ..constants.commands import CMD_TRADE, CMD_TRADE_RESULT
from ..constants.orders import (
    EXEC_MARKET, FILLING_FOK, FILLING_RETURN, FLAGS_XA, ORDER_BUY, ORDER_BUY_LIMIT,
    ORDER_BUY_STOP, ORDER_SELL, ORDER_SELL_LIMIT, ORDER_SELL_STOP, TRADE_ACTION_MODIFY,
    TRADE_ACTION_PENDING, TRADE_ACTION_REMOVE, TRADE_ACTION_SLTP,
)
from ..models import TradeAck, TradeResult
from ..parsers import parse_trade_ack, parse_trade_result
from ..protocol import BUFFER, FLOAT64, INT64, UINT32, UINT64, WCHAR, serialize, vol_to_raw
from .base import BaseService

TradeOutcome = Union[TradeAck, TradeResult, None]


class TradingService(BaseService):
    def trade(self, order_type: int, symbol: str, lots: float, price: float = 0.0,
              sl: float = 0.0, tp: float = 0.0, comment: str = "", position: int = 0,
              position_by: int = 0, exec_mode: int = EXEC_MARKET, filling_ea: int = FILLING_FOK,
              flags: int = FLAGS_XA, deviation: int = 0, order: int = 0,
              price_trigger: float = 0.0, type_time: int = 0, expiration: int = 0) -> Optional[TradeAck]:
        """Send a raw trade request and return the server's immediate acknowledgement.

        Field order follows the official web terminal: price, trigger price (stop-limit),
        SL, TP, then deviation. ``digits`` is taken from the symbol table when known.
        """
        sym = self.state.symbol_map.get(symbol)
        payload = serialize([
            [UINT32, 0],
            [UINT32, exec_mode],
            [WCHAR, symbol, 64],
            [UINT64, vol_to_raw(lots)],
            [UINT32, sym.digits if sym else 0],
            [INT64, order],
            [UINT32, order_type],
            [UINT32, filling_ea],
            [UINT32, type_time],
            [UINT32, flags],
            [UINT32, 0],
            [FLOAT64, price],
            [FLOAT64, price_trigger],
            [FLOAT64, sl],
            [FLOAT64, tp],
            [UINT32, deviation],
            [FLOAT64, 0.0],
            [FLOAT64, 0.0],
            [WCHAR, comment, 64],
            [UINT64, position],
            [UINT64, position_by],
            [UINT32, expiration],
        ])
        resp = self.request(CMD_TRADE, payload, timeout=15)
        return parse_trade_ack(resp) if resp else None

    def wait_trade_result(self, timeout: float = 30) -> Optional[TradeResult]:
        """Block until a final execution report arrives or ``timeout`` elapses.

        Uses ``Session.recv`` so the report reaches this caller even while the tick
        listener owns the socket.
        """
        deadline = time.time() + timeout
        while True:
            remaining = deadline - time.time()
            if remaining <= 0:
                return None
            msg = self.session.recv(CMD_TRADE_RESULT, timeout=remaining)
            if msg is None:
                return None
            result = parse_trade_result(msg.payload)
            if result is not None:
                return result

    def _execute(self, ack: Optional[TradeAck]) -> TradeOutcome:
        if ack and ack.retcode == 0:
            return self.wait_trade_result()
        return ack

    def buy(self, symbol: str, lots: float, sl: float = 0.0, tp: float = 0.0, comment: str = "") -> TradeOutcome:
        return self._execute(self.trade(ORDER_BUY, symbol, lots, comment=comment, sl=sl, tp=tp))

    def sell(self, symbol: str, lots: float, sl: float = 0.0, tp: float = 0.0, comment: str = "") -> TradeOutcome:
        return self._execute(self.trade(ORDER_SELL, symbol, lots, comment=comment, sl=sl, tp=tp))

    def _pending(self, order_type: int, symbol: str, lots: float, price: float,
                 sl: float, tp: float, comment: str) -> TradeOutcome:
        return self._execute(self.trade(
            order_type, symbol, lots, price=price, sl=sl, tp=tp, comment=comment,
            exec_mode=TRADE_ACTION_PENDING, filling_ea=FILLING_RETURN))

    def buy_limit(self, symbol: str, lots: float, price: float, sl: float = 0.0, tp: float = 0.0, comment: str = "") -> TradeOutcome:
        return self._pending(ORDER_BUY_LIMIT, symbol, lots, price, sl, tp, comment)

    def sell_limit(self, symbol: str, lots: float, price: float, sl: float = 0.0, tp: float = 0.0, comment: str = "") -> TradeOutcome:
        return self._pending(ORDER_SELL_LIMIT, symbol, lots, price, sl, tp, comment)

    def buy_stop(self, symbol: str, lots: float, price: float, sl: float = 0.0, tp: float = 0.0, comment: str = "") -> TradeOutcome:
        return self._pending(ORDER_BUY_STOP, symbol, lots, price, sl, tp, comment)

    def sell_stop(self, symbol: str, lots: float, price: float, sl: float = 0.0, tp: float = 0.0, comment: str = "") -> TradeOutcome:
        return self._pending(ORDER_SELL_STOP, symbol, lots, price, sl, tp, comment)

    def modify_sl_tp(self, symbol: str, position_ticket: int, sl: float = 0.0, tp: float = 0.0) -> TradeOutcome:
        return self._execute(self.trade(
            ORDER_BUY, symbol, 0.0, sl=sl, tp=tp, position=position_ticket,
            exec_mode=TRADE_ACTION_SLTP, filling_ea=FILLING_RETURN))

    def _pending_params(self, order_ticket: int) -> tuple[int, float, float]:
        """``(type, price, volume)`` of an active pending order; the server requires them on modify/remove."""
        o = self.state.book.pending.get(order_ticket)
        if o is None:
            from ..constants.commands import CMD_INIT_TRADING
            from ..parsers import parse_pending_orders
            resp = self.request(CMD_INIT_TRADING, timeout=10)
            if resp:
                o = next((x for x in parse_pending_orders(resp.payload) if x.ticket == order_ticket), None)
        return (o.type_id, o.price, o.volume) if o else (ORDER_BUY, 0.0, 0.0)

    def modify_pending(self, symbol: str, order_ticket: int, price: float, sl: float = 0.0, tp: float = 0.0,
                       order_type: Optional[int] = None, lots: Optional[float] = None) -> TradeOutcome:
        """Change a pending order. Type and volume are looked up when not given."""
        if order_type is None or lots is None:
            t, _, v = self._pending_params(order_ticket)
            order_type = t if order_type is None else order_type
            lots = v if lots is None else lots
        return self._execute(self.trade(
            order_type, symbol, lots, price=price, sl=sl, tp=tp, order=order_ticket,
            exec_mode=TRADE_ACTION_MODIFY, filling_ea=FILLING_RETURN))

    def cancel_order(self, symbol: str, order_ticket: int, order_type: Optional[int] = None,
                     price: Optional[float] = None, lots: Optional[float] = None) -> TradeOutcome:
        """Remove a pending order. The server rejects (ORDER_LOCKED) unless type, price and volume match."""
        if order_type is None or price is None or lots is None:
            t, p, v = self._pending_params(order_ticket)
            order_type = t if order_type is None else order_type
            price = p if price is None else price
            lots = v if lots is None else lots
        return self._execute(self.trade(
            order_type, symbol, lots, price=price, order=order_ticket,
            exec_mode=TRADE_ACTION_REMOVE, filling_ea=FILLING_RETURN))

    def close_position(self, symbol: str, ticket: int, lots: Optional[float] = None, pos_type: str = 'BUY') -> TradeOutcome:
        """Close by opening the opposite side against ``ticket``. ``lots`` defaults to 0.01."""
        if lots is None:
            lots = 0.01
        close_dir = ORDER_SELL if pos_type == 'BUY' else ORDER_BUY
        return self._execute(self.trade(close_dir, symbol, lots, position=ticket))

    def close_by_order(self, symbol: str, order_ticket: int, lots: float, pos_type: str = 'BUY') -> TradeOutcome:
        close_dir = ORDER_SELL if pos_type == 'BUY' else ORDER_BUY
        return self._execute(self.trade(close_dir, symbol, lots, position=order_ticket))
