from typing import Optional

from ..models import AccountInfo, AccountSummary, Frame, Position
from ..protocol import BinaryReader
from ..protocol.layouts import ACCOUNT_MIN_SIZE


def parse_account(frame: Optional[Frame]) -> Optional[AccountInfo]:
    """``None`` unless the frame is a successful reply of at least 89 bytes.

    Fields beyond the first 89 bytes are read only when the payload is long enough.
    """
    if frame is None or frame.status != 0 or len(frame.payload) < ACCOUNT_MIN_SIZE:
        return None
    z = frame.payload
    r = BinaryReader(z)
    n = len(z)
    group = r.wchar(97, 256) if n >= 353 else ""
    return AccountInfo(
        balance=r.f64(9),
        credit=r.f64(17),
        currency=r.wchar(25, 64),
        raw=frame,
        account_type=r.u32(89) if n >= 97 else 0,
        leverage=r.u32(93) if n >= 97 else 0,
        group=group,
        server_id=r.u16(353) if n >= 355 else 0,
        server=r.wchar(355, 128) if n >= 483 else "",
        company=r.wchar(483, 128) if n >= 611 else "",
        stopout_level=r.f64(752) if n >= 760 else 0.0,
    )


def summarize_account(account: AccountInfo, positions: list[Position]) -> AccountSummary:
    """Equity and margin from the account record plus the open positions' server-side values."""
    profit = sum(p.profit for p in positions)
    margin = sum(p.margin for p in positions)
    equity = account.balance + account.credit + profit
    return AccountSummary(
        account=account,
        equity=equity,
        margin=margin,
        free_margin=equity - margin,
        margin_level=(equity / margin * 100) if margin > 0 else 0.0,
        profit=profit,
        positions_count=len(positions),
    )
