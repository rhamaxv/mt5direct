from dataclasses import dataclass

from .frame import Frame


@dataclass(frozen=True, slots=True)
class AccountInfo:
    balance: float
    credit: float
    currency: str
    raw: Frame
