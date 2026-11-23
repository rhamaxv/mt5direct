import struct
import threading
import time
from typing import Callable, Optional, Union

from ..constants.commands import CMD_CANDLES, CMD_TICK
from ..constants.timeframes import TF_SECONDS, TIMEFRAMES
from ..models import Candle, Tick
from ..parsers import parse_candles, parse_tick, parse_ticks
from ..protocol import WCHAR, serialize
from .auth import AuthService
from .base import BaseService

TickCallback = Callable[[Tick], None]

_MIN_CANDLE_WINDOW = 7 * 86400
_RECONNECT_BACKOFF = 5


class MarketDataService(BaseService):
    def __init__(self, session, state, auth: AuthService):
        super().__init__(session, state)
        self._auth = auth
        self._tick_callbacks: list[TickCallback] = []
        self._running = False

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

    def parse_tick(self, data: bytes, offset: int = 0) -> Optional[Tick]:
        return parse_tick(data, offset, self.state.ta_to_sym)

    def parse_ticks(self, payload: bytes) -> list[Tick]:
        return parse_ticks(payload, self.state.ta_to_sym)

    def on_tick(self, callback: TickCallback) -> None:
        self._tick_callbacks.append(callback)

    def start_tick_listener(self, symbols=None) -> threading.Thread:
        """Dispatch incoming ticks to ``on_tick`` callbacks on a daemon thread; reconnects on error."""
        self._running = True

        def _loop():
            while self._running:
                try:
                    msg = self.session.recv_any(timeout=1)
                    if msg and msg.cmd == CMD_TICK:
                        for tick in self.parse_ticks(msg.payload):
                            for cb in self._tick_callbacks:
                                try:
                                    cb(tick)
                                except Exception:
                                    pass
                except Exception:
                    if self._running:
                        try:
                            self._auth.auto_reconnect()
                        except Exception:
                            time.sleep(_RECONNECT_BACKOFF)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()
        return t

    def stop_tick_listener(self) -> None:
        self._running = False
