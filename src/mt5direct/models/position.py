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
    swap: float = 0.0
    commission: float = 0.0
    time_open: int = 0
    magic: int = 0
    comment: str = ""
    digits: int = 0
    margin: float = 0.0
    """``volume × contract_size × price_current / leverage``; 0 when leverage is unknown."""


@dataclass(frozen=True, slots=True)
class PendingOrder:
    """An active pending order from the init-trading reply. Layout is partially known."""

    ticket: int
    symbol: str
    price: float
    time: int
    comment: str


@dataclass(frozen=True, slots=True)
class PositionPnL:
    """A position with a live price and the floating P&L computed from it."""

    position: Position
    current_price: float
    pnl: float
