from dataclasses import dataclass

from .frame import Frame


@dataclass(frozen=True, slots=True)
class AccountInfo:
    """Static account record from the server. Live equity/margin live in ``AccountSummary``."""

    balance: float
    credit: float
    currency: str
    raw: Frame
    account_type: int = 0
    """2 = demo on the servers observed so far."""
    leverage: int = 0
    group: str = ""
    server_id: int = 0
    server: str = ""
    company: str = ""
    stopout_level: float = 0.0


@dataclass(frozen=True, slots=True)
class AccountSummary:
    """``AccountInfo`` plus equity and margin computed from the open positions."""

    account: AccountInfo
    equity: float
    margin: float
    free_margin: float
    margin_level: float
    profit: float
    positions_count: int
