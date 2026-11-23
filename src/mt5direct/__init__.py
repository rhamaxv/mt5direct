"""mt5direct: standalone MetaTrader 5 client over the native WebSocket protocol."""

from .client import MT5Client
from .constants import *  # noqa: F401,F403
from .exceptions import ConnectionFailed, LoginFailed, MT5Error
from .models import (
    AccountInfo, Candle, Deal, Frame, HistoryOrder, Position, PositionPnL, Symbol, Tick,
    TradeAck, TradeResult,
)

from ._version import __version__  # noqa: E402

__all__ = [
    "MT5Client", "__version__",
    "MT5Error", "ConnectionFailed", "LoginFailed",
    "AccountInfo", "Candle", "Deal", "Frame", "HistoryOrder", "Position", "PositionPnL",
    "Symbol", "Tick", "TradeAck", "TradeResult",
]
