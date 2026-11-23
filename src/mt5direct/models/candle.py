from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Candle:
    time: int
    open: float
    high: float
    low: float
    close: float
    tick_volume: int
    spread: int
