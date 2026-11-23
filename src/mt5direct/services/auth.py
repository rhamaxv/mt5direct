import hashlib
from typing import Optional

from ..constants.commands import CMD_LOGIN, CMD_PING
from ..constants.network import TRADE_HOSTS
from ..exceptions import LoginFailed
from ..models import Frame
from ..protocol import BUFFER, UINT32, UINT64, WCHAR, serialize
from .account import AccountService
from .base import BaseService
from .symbols import SymbolService

_DEVICE_FINGERPRINT = b'Python;1;en-US;1920x1080;mt5standalone'


class AuthService(BaseService):
    def __init__(self, session, state, symbols: SymbolService, account: AccountService):
        super().__init__(session, state)
        self._symbols = symbols
        self._account = account

    def _reconnect_hosts(self) -> list[str]:
        return list(dict.fromkeys([*self.state.preferred_hosts, *TRADE_HOSTS]))

    def login(self, login_id: int, password: str) -> Frame:
        device_hash = hashlib.sha1(_DEVICE_FINGERPRINT).digest()[:16]
        payload = serialize([
            [UINT32, 0],
            [WCHAR, password, 64],
            [WCHAR, '', 128],
            [BUFFER, device_hash, 16],
            [WCHAR, '', 64],
            [WCHAR, '', 64],
            [UINT64, 0],
            [WCHAR, '', 128],
            [UINT32, 0],
            [WCHAR, '', 256],
            [UINT64, login_id],
            [BUFFER, b'\x00' * 160, 160],
            [UINT64, 0],
        ])
        resp = self.request(CMD_LOGIN, payload)
        if resp is None or resp.status != 0:
            raise LoginFailed(f"Login failed: dd={resp.status if resp else 'timeout'}")
        self.state.login_id = login_id
        self.state.password = password
        return resp

    def ping(self) -> Optional[Frame]:
        return self.request(CMD_PING, timeout=5)

    def reconnect(self, login_id: Optional[int] = None, password: Optional[str] = None) -> bool:
        """Try the preferred host, then each known host; log in if credentials are given."""
        self.session.close()
        for host in self._reconnect_hosts():
            try:
                self.session.address = host
                self.session.connect()
                if login_id and password:
                    self.login(login_id, password)
                return True
            except Exception:
                continue
        return False

    def auto_reconnect(self) -> bool:
        """Reconnect with stored credentials and restore symbols, trading state and subscriptions."""
        self.session.close()
        for host in self._reconnect_hosts():
            try:
                self.session.address = host
                self.session.connect()
                if self.state.login_id and self.state.password:
                    self.login(self.state.login_id, self.state.password)
                self._symbols.get_symbols()
                self._account.init_trading()
                self._symbols.subscribe_all()
                return True
            except Exception:
                continue
        return False
