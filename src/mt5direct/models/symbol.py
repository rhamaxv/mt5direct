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
