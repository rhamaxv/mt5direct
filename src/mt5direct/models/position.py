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


@dataclass(frozen=True, slots=True)
class PositionPnL:
    """A position with a live price and the floating P&L computed from it."""

    position: Position
    current_price: float
    pnl: float
