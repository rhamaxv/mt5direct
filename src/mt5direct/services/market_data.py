import logging
import struct
import threading
import time
from typing import Callable, Optional, Union

from ..constants.commands import CMD_CANDLES, CMD_INIT_TRADING, CMD_TICK, CMD_TRADE_RESULT, CMD_TRADE_TRANSACTION
from ..constants.timeframes import TF_SECONDS, TIMEFRAMES
from ..models import Candle, Frame, Position, Tick, TradeResult, TradeTransaction
from ..parsers import (
    parse_candles, parse_pending_orders, parse_positions, parse_tick, parse_ticks, parse_trade_result,
    parse_trade_transactions,
)
from ..protocol import WCHAR, serialize
from .auth import AuthService
from .base import BaseService

log = logging.getLogger("mt5direct.market")

TickCallback = Callable[[Tick], None]
TradeCallback = Callable[[TradeResult], None]
PositionsCallback = Callable[[list[Position]], None]
TransactionCallback = Callable[[TradeTransaction], None]

_MIN_CANDLE_WINDOW = 7 * 86400
_RECONNECT_BACKOFF = 5


class MarketDataService(BaseService):
    """Candles, the tick/event listener thread, and the heartbeat thread."""

    def __init__(self, session, state, auth: AuthService):
        super().__init__(session, state)
        self._auth = auth
        self._tick_callbacks: list[TickCallback] = []
        self._trade_callbacks: list[TradeCallback] = []
        self._position_callbacks: list[PositionsCallback] = []
        self._transaction_callbacks: list[TransactionCallback] = []
        self._running = False
        self._heartbeat_running = False

    # -- candles --------------------------------------------------------------------

    def get_candles(self, symbol: str, timeframe: Union[str, int] = 'H1', count: int = 1000,
                    from_ts: Optional[int] = None, to_ts: Optional[int] = None) -> list[Candle]:
        """Fetch up to ``count`` most recent candles. Window defaults to 3x the span, min 7 days."""
        if isinstance(timeframe, str):
            tf_val = TIMEFRAMES.get(timeframe.upper())
            if tf_val is None:
                raise ValueError(f"Unknown timeframe: {timeframe}. Use: {list(TIMEFRAMES.keys())}")
        else:
            tf_val = timeframe
        if to_ts is None:
            to_ts = int(time.time())
        if from_ts is None:
            sec = TF_SECONDS.get(tf_val, 3600)
            window = count * sec * 3
            if window < _MIN_CANDLE_WINDOW:
                window = _MIN_CANDLE_WINDOW
            from_ts = max(0, to_ts - window)
        payload = serialize([[WCHAR, symbol, 64]])
        payload += struct.pack('<H', tf_val)
        payload += struct.pack('<II', from_ts, to_ts)
        resp = self.request(CMD_CANDLES, payload, timeout=30)
        if not resp:
            return []
        candles = parse_candles(resp.payload)
        if count and len(candles) > count:
            candles = candles[-count:]
        return candles

    def get_candles_df(self, symbol: str, timeframe: Union[str, int] = 'H1', count: int = 1000, **kwargs):
        """``get_candles`` as a pandas DataFrame indexed by UTC time. Requires ``pip install mt5direct[pandas]``."""
        try:
            import pandas as pd
        except ImportError as e:
            raise ImportError("pandas is required: pip install 'mt5direct[pandas]'") from e
        candles = self.get_candles(symbol, timeframe, count, **kwargs)
        if not candles:
            return pd.DataFrame()
        df = pd.DataFrame([c.__dict__ if hasattr(c, '__dict__') else
                           {f: getattr(c, f) for f in c.__slots__} for c in candles])
        df['time'] = pd.to_datetime(df['time'], unit='s', utc=True)
        return df.set_index('time')

    # -- ticks ----------------------------------------------------------------------

    def parse_tick(self, data: bytes, offset: int = 0) -> Optional[Tick]:
        return parse_tick(data, offset, self.state.ta_to_sym)

    def parse_ticks(self, payload: bytes) -> list[Tick]:
        return parse_ticks(payload, self.state.ta_to_sym)

    # -- events ---------------------------------------------------------------------

    def on_tick(self, callback: TickCallback) -> None:
        self._tick_callbacks.append(callback)

    def off_tick(self, callback: TickCallback) -> None:
        if callback in self._tick_callbacks:
            self._tick_callbacks.remove(callback)

    @property
    def listener_running(self) -> bool:
        return self._running

    def on_trade(self, callback: TradeCallback) -> None:
        """Every execution report the server pushes, including in-flight codes."""
        self._trade_callbacks.append(callback)

    def on_position_change(self, callback: PositionsCallback) -> None:
        """Called with the current open positions after every event that changes them."""
        self._position_callbacks.append(callback)

    def on_transaction(self, callback: TransactionCallback) -> None:
        """Every trade transaction the server pushes: order changes, deals, position updates."""
        self._transaction_callbacks.append(callback)

    def dispatch(self, frame: Frame) -> None:
        """Route one pushed frame: ticks, trade results, trade transactions, position snapshots."""
        if frame.cmd == CMD_TICK:
            for tick in self.parse_ticks(frame.payload):
                self._emit(self._tick_callbacks, tick, "tick")
        elif frame.cmd == CMD_TRADE_RESULT:
            result = parse_trade_result(frame.payload, include_in_flight=True)
            if result:
                self._emit(self._trade_callbacks, result, "trade")
        elif frame.cmd == CMD_TRADE_TRANSACTION:
            book = self.state.book
            changed = False
            for tx in parse_trade_transactions(frame.payload, self.state.leverage):
                book.apply(tx)
                changed = changed or tx.position is not None
                self._emit(self._transaction_callbacks, tx, "transaction")
            if changed and self._position_callbacks:
                self._emit(self._position_callbacks, list(book.positions.values()), "position")
        elif frame.cmd == CMD_INIT_TRADING:
            self.state.book.seed(parse_positions(frame.payload, self.state.leverage),
                                 parse_pending_orders(frame.payload))
            if self._position_callbacks:
                self._emit(self._position_callbacks, list(self.state.book.positions.values()), "position")

    def pump(self, max_wait: float = 0.3) -> int:
        """Read and dispatch frames already available on the socket (no listener running).

        Returns the number of frames handled. Lets ``get_positions`` reflect trades made
        on this connection without a background thread.
        """
        if self._running:
            return 0
        handled = 0
        deadline = time.time() + max_wait
        while time.time() < deadline:
            frame = self.session.recv_any(timeout=0.05)
            if frame is None:
                break
            self.dispatch(frame)
            handled += 1
        return handled

    @staticmethod
    def _emit(callbacks, value, kind: str) -> None:
        for cb in callbacks:
            try:
                cb(value)
            except Exception as e:
                log.warning("%s callback error: %s", kind, e)

    # -- listener -------------------------------------------------------------------

    def start_tick_listener(self, symbols=None) -> threading.Thread:
        """Read frames on a daemon thread and dispatch them; reconnects on socket errors.

        While it runs it owns the socket: requests from other threads (``ping``, ``buy``, ...)
        receive their replies through the session queue.
        """
        self._running = True

        def _loop():
            while self._running:
                try:
                    frame = self.session.recv_any(timeout=1)
                    if frame:
                        self.dispatch(frame)
                except Exception as e:
                    log.error("listener error: %s", e)
                    if self._running:
                        try:
                            self._auth.auto_reconnect()
                        except Exception as e2:
                            log.error("reconnect failed: %s", e2)
                            time.sleep(_RECONNECT_BACKOFF)
            self.session.detach_reader()

        t = threading.Thread(target=_loop, name="mt5direct-listener", daemon=True)
        self.session.attach_reader(t)
        t.start()
        return t

    def stop_tick_listener(self) -> None:
        self._running = False

    # -- heartbeat ------------------------------------------------------------------

    def start_heartbeat(self, interval: float = 30) -> threading.Thread:
        """Ping every ``interval`` seconds on a daemon thread; auto-reconnect after two consecutive failures."""
        self._heartbeat_running = True

        def _hb():
            failures = 0
            while self._heartbeat_running:
                time.sleep(interval)
                if not self._heartbeat_running:
                    break
                try:
                    if self._auth.ping() is None:
                        raise TimeoutError("ping timed out")
                    failures = 0
                    log.debug("heartbeat OK")
                except Exception as e:
                    failures += 1
                    log.warning("heartbeat failed (%d): %s", failures, e)
                    if failures >= 2 and self._heartbeat_running:
                        try:
                            self._auth.auto_reconnect()
                            failures = 0
                        except Exception as e2:
                            log.error("heartbeat reconnect failed: %s", e2)

        t = threading.Thread(target=_hb, name="mt5direct-heartbeat", daemon=True)
        t.start()
        return t

    def stop_heartbeat(self) -> None:
        self._heartbeat_running = False

    def stop(self) -> None:
        self._running = False
        self._heartbeat_running = False
