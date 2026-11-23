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
    order: int = 0
    commission: float = 0.0
    swap: float = 0.0
    fee: float = 0.0
    comment: str = ""
    magic: int = 0


@dataclass(frozen=True, slots=True)
class HistoryOrder:
    order: int
    time: int = 0
    symbol: str = ""
    type: str = ""
    """``'BUY'``, ``'SELL_LIMIT'``, ... see ``constants.orders.ORDER_TYPE_NAMES``."""
    state: str = ""
    """``'PLACED'``, ``'FILLED'``, ... see ``constants.orders.ORDER_STATE_NAMES``."""
    price: float = 0.0
    volume: float = 0.0
    sl: float = 0.0
    tp: float = 0.0
    comment: str = ""
