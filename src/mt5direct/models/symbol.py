from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Symbol:
    name: str
    description: str
    index: int
    ta: int
    """Server-side numeric id used for resolve/subscribe and in tick records."""
    digits: int
    path: str


@dataclass(frozen=True, slots=True)
class SymbolInfo:
    """Trading specification from the resolve record."""

    name: str
    digits: int
    description: str
    path: str
    trade_mode: str
    """``'DISABLED'``, ``'LONGONLY'``, ``'SHORTONLY'``, ``'CLOSEONLY'`` or ``'FULL'``."""
    trade_mode_id: int
    contract_size: float
    tick_size: float
    """``10 ** -digits``."""
    tick_value: float
    """``contract_size × tick_size``."""
    volume_min: float
    volume_max: float
    volume_step: float
