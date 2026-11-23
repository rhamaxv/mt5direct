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
    position_id: int = 0
    price_position: float = 0.0
    """Open price of the position this deal belongs to (0 on entry deals)."""
    comment: str = ""
    contract_size: float = 0.0
    digits: int = 0


@dataclass(frozen=True, slots=True)
class HistoryOrder:
    order: int
    symbol: str = ""
    type: str = ""
    """``'BUY'``, ``'SELL_LIMIT'``, ... see ``constants.orders.ORDER_TYPE_NAMES``."""
    type_id: int = 0
    state: str = ""
    """``'PLACED'``, ``'FILLED'``, ``'CANCELED'``, ... see ``constants.orders.ORDER_STATE_NAMES``."""
    state_id: int = 0
    time_setup: int = 0
    time_done: int = 0
    price: float = 0.0
    """Order price; 0 for market orders."""
    price_current: float = 0.0
    """Market price at the last update; the fill price for market orders."""
    volume: float = 0.0
    volume_current: float = 0.0
    position_id: int = 0
    comment: str = ""
    type_filling: int = 0
    contract_size: float = 0.0
    digits: int = 0
