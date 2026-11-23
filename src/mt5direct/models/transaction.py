from dataclasses import dataclass
from typing import Optional

from .history import Deal, HistoryOrder
from .position import Position

KIND_ORDER = 0
"""An active order changed (placed, filled, canceled, modified)."""
KIND_ORDER_HISTORY = 1
"""An order was written to history."""
KIND_DEAL = 2
"""A deal happened or a position changed; carries the position and the account balance."""


@dataclass(frozen=True, slots=True)
class TradeTransaction:
    """One trade event pushed by the server (cmd 10)."""

    kind: int
    seq: int
    flag: int
    order: Optional[HistoryOrder] = None
    deal: Optional[Deal] = None
    position: Optional[Position] = None
    position_removed: bool = False
    """Set when the position record arrives emptied (volume 0): the position is closed."""
    balance: Optional[float] = None
