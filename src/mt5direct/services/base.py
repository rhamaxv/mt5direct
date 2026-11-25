import os
from dataclasses import dataclass, field
from typing import Callable, Optional

from ..exceptions import ConnectionLost
from ..models import Frame, PendingOrder, Position, Symbol, TradeTransaction
from ..models.transaction import KIND_DEAL, KIND_ORDER
from ..transport import Session


@dataclass
class PositionBook:
    """Open positions and pending orders, seeded from the login snapshot and kept
    current by trade transaction pushes (cmd 10). The snapshot itself never changes
    during a session, so this is the only reliable source after the first trade."""

    positions: dict[int, Position] = field(default_factory=dict)
    pending: dict[int, PendingOrder] = field(default_factory=dict)
    balance: Optional[float] = None
    seeded: bool = False

    def seed(self, positions: list[Position], pending: list[PendingOrder]) -> None:
        self.positions = {p.ticket: p for p in positions}
        self.pending = {o.ticket: o for o in pending}
        self.seeded = True

    def apply(self, tx: TradeTransaction) -> None:
        if tx.kind == KIND_DEAL and tx.position is not None:
            if tx.position_removed:
                self.positions.pop(tx.position.ticket, None)
            else:
                self.positions[tx.position.ticket] = tx.position
            if tx.balance is not None:
                self.balance = tx.balance
        elif tx.kind == KIND_ORDER and tx.order is not None:
            o = tx.order
            if o.state_id in (0, 1, 3) and o.type_id >= 2:     # started / placed / partial pending order
                self.pending[o.order] = PendingOrder(
                    ticket=o.order, symbol=o.symbol, type=o.type, type_id=o.type_id, price=o.price,
                    price_current=o.price_current, volume=o.volume, volume_current=o.volume_current,
                    time_setup=o.time_setup, comment=o.comment, sl=o.sl, tp=o.tp, state=o.state,
                    state_id=o.state_id, type_filling=o.type_filling, contract_size=o.contract_size,
                    digits=o.digits)
            else:
                self.pending.pop(o.order, None)


@dataclass
class ClientState:
    """Mutable state shared by all services of one client."""

    symbols: list[Symbol] = field(default_factory=list)
    symbol_map: dict[str, Symbol] = field(default_factory=dict)
    ta_to_sym: dict[int, Symbol] = field(default_factory=dict)
    login_id: Optional[int] = None
    password: Optional[str] = None
    login_token: Optional[bytes] = None
    """160-byte session token from the last login reply; re-login without the password."""
    login_um: int = 0
    """u64 that follows the token in the login reply; sent back with the token."""
    device_hash: bytes = field(default_factory=lambda: os.urandom(16))
    """Per-client device id sent in every login; the token is bound to it."""
    leverage: int = 0
    """From the last ``get_account_info``; used for position margin."""
    book: "PositionBook" = field(default_factory=lambda: PositionBook())
    after_login: Optional[Callable[[], None]] = None
    """Called after every successful login, e.g. to rewrite a saved session with the fresh token."""
    preferred_hosts: list[str] = field(default_factory=list)
    """``host[:port]`` entries tried before ``TRADE_HOSTS`` on reconnect, e.g. the resolved server host."""

    def set_symbols(self, symbols: list[Symbol]) -> None:
        self.symbols = symbols
        self.symbol_map = {s.name: s for s in symbols}
        self.ta_to_sym = {s.ta: s for s in symbols}


class BaseService:
    def __init__(self, session: Session, state: ClientState):
        self.session = session
        self.state = state

    def request(self, cmd: int, payload: bytes = b'', timeout: float = 15) -> Optional[Frame]:
        """Send ``cmd`` and wait for the matching reply (stale pushed frames are discarded).

        ``None`` on timeout or if the connection is gone; callers never see socket errors.
        """
        try:
            return self.session.request(cmd, payload, timeout=timeout)
        except ConnectionLost:
            return None
