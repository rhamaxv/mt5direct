from dataclasses import dataclass
from typing import Optional

from .frame import Frame


@dataclass(frozen=True, slots=True)
class TradeAck:
    """Immediate reply to a trade request. ``retcode`` is ``None`` if the reply had no code."""

    retcode: Optional[int]
    retcode_str: Optional[str]
    raw: Frame


@dataclass(frozen=True, slots=True)
class TradeResult:
    """Execution report pushed by the server. Only the ``retcode`` fields are meaningful unless filled."""

    retcode: int
    retcode_str: str
    deal: int = 0
    order: int = 0
    volume: float = 0.0
    volume_raw: int = 0
    price: float = 0.0
    bid: float = 0.0
    ask: float = 0.0
    comment: str = ""

    @property
    def filled(self) -> bool:
        return self.retcode in (10009, 10011)

    @property
    def in_flight(self) -> bool:
        return self.retcode in (10001, 10002, 10003)
