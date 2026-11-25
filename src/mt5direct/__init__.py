"""mt5direct: standalone MetaTrader 5 client over the native WebSocket protocol."""

from .aio import AsyncMT5Client
from .client import MT5Client
from .constants import *  # noqa: F401,F403
from .discovery import Endpoint, Registry, discover_from_url, list_servers, load_registry, resolve_server
from .exceptions import ConnectionFailed, LoginFailed, MT5Error, ServerNotFound
from .sessions import SavedSession
from .models import (
    AccountInfo, AccountSummary, Candle, Deal, Frame, HistoryOrder, PendingOrder, Position,
    PositionPnL, Symbol, SymbolInfo, Tick, TradeAck, TradeResult, TradeTransaction,
)

from ._version import __version__  # noqa: E402

__all__ = [
    "MT5Client", "AsyncMT5Client", "__version__",
    "MT5Error", "ConnectionFailed", "LoginFailed", "ServerNotFound",
    "SavedSession", "Endpoint", "Registry", "discover_from_url", "list_servers", "load_registry", "resolve_server",
    "AccountInfo", "AccountSummary", "Candle", "Deal", "Frame", "HistoryOrder", "PendingOrder",
    "Position", "PositionPnL", "Symbol", "SymbolInfo", "Tick", "TradeAck", "TradeResult", "TradeTransaction",
]
