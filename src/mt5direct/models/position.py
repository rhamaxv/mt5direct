from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Position:
    ticket: int
    symbol: str
    type: str
    """``'BUY'`` or ``'SELL'``."""
    volume: float
    price_open: float
    price_current: float
    sl: float
    tp: float
    contract_size: float
    profit: float = 0.0
    """Server-side floating profit."""
    time_open: int = 0
    comment: str = ""
    digits: int = 0
    margin: float = 0.0
    """``volume × contract_size × price_current / leverage``; 0 when leverage is unknown."""


@dataclass(frozen=True, slots=True)
class PendingOrder:
    """An active pending order from the init-trading reply (same 356-byte layout as ``HistoryOrder``)."""

    ticket: int
    symbol: str
    type: str
    type_id: int
    price: float
    price_current: float
    volume: float
    volume_current: float
    time_setup: int
    comment: str
    sl: float = 0.0
    tp: float = 0.0
    state: str = "PLACED"
    state_id: int = 1
    type_filling: int = 0
    contract_size: float = 0.0
    digits: int = 0


@dataclass(frozen=True, slots=True)
class PositionPnL:
    """A position with a live price and the floating P&L computed from it."""

    position: Position
    current_price: float
    pnl: float
