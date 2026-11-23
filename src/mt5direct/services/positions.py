import time
from typing import Callable, Optional

from ..constants.commands import CMD_INIT_TRADING, CMD_TICK
from ..constants.retcodes import RETCODE_DONE, RETCODE_DONE_PARTIAL
from ..models import PendingOrder, Position, PositionPnL
from ..parsers import parse_pending_orders, parse_positions, parse_ticks
from .base import BaseService
from .market_data import MarketDataService
from .trading import TradingService

PnLCallback = Callable[[list[PositionPnL]], None]


class PositionService(BaseService):
    def __init__(self, session, state, trading: TradingService, market: MarketDataService):
        super().__init__(session, state)
        self._trading = trading
        self._market = market

    def _init_payload(self) -> bytes:
        resp = self.request(CMD_INIT_TRADING, timeout=10)
        return resp.payload if resp else b''

    def get_positions(self) -> list[Position]:
        return parse_positions(self._init_payload(), self.state.leverage)

    def get_pending_orders(self) -> list[PendingOrder]:
        """Active pending orders. Layout is partially known; see ``parse_pending_orders``."""
        return parse_pending_orders(self._init_payload())

    def get_positions_and_orders(self) -> tuple[list[Position], list[PendingOrder]]:
        """Both lists from one round-trip."""
        payload = self._init_payload()
        return parse_positions(payload, self.state.leverage), parse_pending_orders(payload)

    def close_all(self, symbol: Optional[str] = None) -> tuple[int, int]:
        """Close every open position (optionally one symbol). Returns ``(closed, total)``."""
        positions = self.get_positions()
        if symbol:
            positions = [p for p in positions if p.symbol == symbol]
        closed = 0
        for p in positions:
            vol = p.volume if p.volume > 0 else 0.01
            r = self._trading.close_position(p.symbol, p.ticket, lots=vol, pos_type=p.type)
            rc = (r.retcode or 0) if r else 0
            deal = getattr(r, 'deal', 0) if r else 0
            if rc in (RETCODE_DONE, RETCODE_DONE_PARTIAL) or deal > 0:
                closed += 1
        return closed, len(positions)

    def track_positions(self, duration: float = 60, callback: Optional[PnLCallback] = None) -> dict:
        """Follow ticks for ``duration`` seconds and report floating P&L of the open positions.

        Reads the socket directly, or subscribes to the tick listener when that is running.
        """
        positions = self.get_positions()
        if not positions:
            return {}
        pos_syms = {p.symbol for p in positions}
        prices: dict[str, dict[str, float]] = {}

        def report() -> None:
            rows = []
            for p in positions:
                pr = prices.get(p.symbol)
                if pr and p.price_open > 0:
                    current = pr['bid'] if p.type == 'BUY' else pr['ask']
                    cs = p.contract_size if p.contract_size > 0 else 1
                    diff = current - p.price_open
                    if p.type == 'SELL':
                        diff = -diff
                    rows.append(PositionPnL(position=p, current_price=current, pnl=diff * p.volume * cs))
            if callback and rows:
                callback(rows)

        def on_tick(tick) -> None:
            if tick.symbol in pos_syms:
                prices[tick.symbol] = {'bid': tick.bid, 'ask': tick.ask}
                report()

        start = time.time()
        if self._market.listener_running:
            self._market.on_tick(on_tick)
            try:
                while time.time() - start < duration:
                    time.sleep(0.2)
            finally:
                self._market.off_tick(on_tick)
            return prices
        while time.time() - start < duration:
            msg = self.session.recv_any(timeout=1)
            if msg and msg.cmd == CMD_TICK:
                for tick in parse_ticks(msg.payload, self.state.ta_to_sym):
                    on_tick(tick)
        return prices
