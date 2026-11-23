from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Deal:
    deal: int
    symbol: str
    time: int
    action: str
    """``'BUY'`` or ``'SELL'``."""
    entry: str
    """``'IN'`` or ``'OUT'``."""
    price: float
    volume: float
    profit: float


@dataclass(frozen=True, slots=True)
class HistoryOrder:
    order: int
