import hashlib
import logging
from typing import Optional

from ..constants.commands import CMD_LOGIN, CMD_PING
from ..constants.network import TRADE_HOSTS
from ..exceptions import LoginFailed
from ..models import Frame
from ..protocol import BUFFER, UINT32, UINT64, WCHAR, serialize
from ..protocol.layouts import LOGIN_TOKEN_SIZE
from .account import AccountService
from .base import BaseService
from .symbols import SymbolService

log = logging.getLogger("mt5direct.auth")

_DEVICE_FINGERPRINT = b'Python;1;en-US;1920x1080;mt5standalone'


def _login_payload(login_id: int, password: str, token: bytes) -> bytes:
    device_hash = hashlib.sha1(_DEVICE_FINGERPRINT).digest()[:16]
    return serialize([
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
        [BUFFER, token[:LOGIN_TOKEN_SIZE], LOGIN_TOKEN_SIZE],
        [UINT64, 0],
    ])


class AuthService(BaseService):
    def __init__(self, session, state, symbols: SymbolService, account: AccountService):
        super().__init__(session, state)
        self._symbols = symbols
        self._account = account

    def _reconnect_hosts(self) -> list[str]:
        return list(dict.fromkeys([*self.state.preferred_hosts, *TRADE_HOSTS]))

    def _do_login(self, login_id: int, password: str, token: bytes, what: str) -> Frame:
        resp = self.request(CMD_LOGIN, _login_payload(login_id, password, token))
        if resp is None or resp.status != 0:
            raise LoginFailed(f"{what} failed: dd={resp.status if resp else 'timeout'}")
        self.state.login_id = login_id
        if len(resp.payload) >= LOGIN_TOKEN_SIZE:
            self.state.login_token = resp.payload[:LOGIN_TOKEN_SIZE]
        log.info("%s OK, account %d", what, login_id)
        return resp

    def login(self, login_id: int, password: str) -> Frame:
        """Password login. Stores the credentials and the session token for reconnects."""
        resp = self._do_login(login_id, password, b'', "Login")
        self.state.password = password
        return resp

    def login_with_token(self, login_id: int, token: Optional[bytes] = None) -> Frame:
        """Re-login with the 160-byte token from a previous login instead of the password."""
        token = token or self.state.login_token
        if not token or len(token) < LOGIN_TOKEN_SIZE:
            raise ValueError("No login token available. Login with password first.")
        return self._do_login(login_id, '', token, "Token login")

    def relogin(self) -> None:
        """Token first, password as fallback. No-op without stored credentials."""
        login_id = self.state.login_id
        if not login_id:
            return
        if self.state.login_token:
            try:
                self.login_with_token(login_id)
                return
            except LoginFailed as e:
                log.debug("token login rejected (%s), falling back to password", e)
                if not self.state.password:
                    raise
        if self.state.password:
            self.login(login_id, self.state.password)

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
            except Exception as e:
                log.debug("reconnect to %s failed: %s", host, e)
                continue
        log.error("reconnect failed on every host")
        return False

    def auto_reconnect(self) -> bool:
        """Reconnect, re-login (token, then password), and restore symbols, trading state and subscriptions."""
        self.session.close()
        for host in self._reconnect_hosts():
            try:
                self.session.address = host
                self.session.connect()
                self.relogin()
                self._symbols.get_symbols()
                self._account.init_trading()
                self._symbols.subscribe_all()
                log.info("auto-reconnect OK via %s", host)
                return True
            except Exception as e:
                log.debug("auto-reconnect via %s failed: %s", host, e)
                continue
        log.error("auto-reconnect failed on every host")
        return False
