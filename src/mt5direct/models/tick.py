from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Tick:
    ta: int
    symbol: str
    digits: int
    bid: float
    ask: float
    bid_raw: float
    ask_raw: float
    last: float
    timestamp: int
    flags: int
    spread: int
