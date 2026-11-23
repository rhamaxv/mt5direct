from dataclasses import dataclass, field
from typing import Optional

from ..models import Frame, Symbol
from ..transport import Session


@dataclass
class ClientState:
    """Mutable state shared by all services of one client."""

    symbols: list[Symbol] = field(default_factory=list)
    symbol_map: dict[str, Symbol] = field(default_factory=dict)
    ta_to_sym: dict[int, Symbol] = field(default_factory=dict)
    login_id: Optional[int] = None
    password: Optional[str] = None
    login_token: Optional[bytes] = None
    """160-byte session token from the last login reply; allows re-login without the password."""
    leverage: int = 0
    """From the last ``get_account_info``; used for position margin."""
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
        """Send ``cmd`` and wait for the matching reply."""
        self.session.send(cmd, payload)
        return self.session.recv(cmd, timeout=timeout)
