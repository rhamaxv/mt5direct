import logging
import struct
import time
from typing import Optional

from ..constants.commands import CMD_LOGIN, CMD_LOGOUT, CMD_PING
from ..constants.network import TRADE_HOSTS
from ..exceptions import LoginFailed
from ..models import Frame
from ..protocol import BUFFER, UINT32, UINT64, WCHAR, serialize
from ..protocol.layouts import LOGIN_TOKEN_SIZE
from .account import AccountService
from .base import BaseService
from .symbols import SymbolService

log = logging.getLogger("mt5direct.auth")

_UM_OFFSET = LOGIN_TOKEN_SIZE


def login_payload(login_id: int, password: str, token: bytes, um: int, device_hash: bytes, host: str) -> bytes:
    """cmd 28 body. Password login: ``password`` set, ``token`` empty. Token login: the reverse."""
    return serialize([
        [UINT32, 0],
        [WCHAR, password, 64],
        [WCHAR, '', 128],
        [BUFFER, device_hash, 16],
        [WCHAR, '', 64],
        [WCHAR, '', 64],
        [UINT64, 0],
        [WCHAR, '', 128],
        [UINT32, min(len(host), 128)],
        [WCHAR, host, 256],
        [UINT64, login_id],
        [BUFFER, token[:LOGIN_TOKEN_SIZE], LOGIN_TOKEN_SIZE],
        [UINT64, um],
        [UINT64, 0],
    ])


class AuthService(BaseService):
    reconnect_min_interval: float = 60.0
    """Seconds between automatic reconnect attempts, so a flapping link cannot hammer the server."""

    def __init__(self, session, state, symbols: SymbolService, account: AccountService):
        super().__init__(session, state)
        self._symbols = symbols
        self._account = account
        self._last_reconnect = 0.0

    def _reconnect_hosts(self) -> list[str]:
        return list(dict.fromkeys([*self.state.preferred_hosts, *TRADE_HOSTS]))

    def _do_login(self, login_id: int, password: str, token: bytes, um: int, what: str) -> Frame:
        payload = login_payload(login_id, password, token, um, self.state.device_hash, self.session.host)
        resp = self.request(CMD_LOGIN, payload)
        if resp is None or resp.status != 0:
            raise LoginFailed(f"{what} failed: dd={resp.status if resp else 'timeout'}")
        self.state.login_id = login_id
        if len(resp.payload) >= LOGIN_TOKEN_SIZE:
            self.state.login_token = resp.payload[:LOGIN_TOKEN_SIZE]
        if len(resp.payload) >= _UM_OFFSET + 8:
            self.state.login_um = struct.unpack_from('<Q', resp.payload, _UM_OFFSET)[0]
        log.info("%s OK, account %d", what, login_id)
        return resp

    def login(self, login_id: int, password: str) -> Frame:
        """Password login. Stores the credentials and the session token for reconnects."""
        resp = self._do_login(login_id, password, b'', 0, "Login")
        self.state.password = password
        return resp

    def login_with_token(self, login_id: int, token: Optional[bytes] = None, um: Optional[int] = None) -> Frame:
        """Re-login with the token from a previous login instead of the password.

        Works only on a connection that sent the device cookie captured with that token
        (``Session.cookie``) and the same ``device_hash``; ``MT5Client.save_session`` /
        ``resume`` keep the three together.
        """
        token = token or self.state.login_token
        um = self.state.login_um if um is None else um
        if not token or len(token) < LOGIN_TOKEN_SIZE:
            raise ValueError("No login token available. Login with password first.")
        return self._do_login(login_id, '', token, um, "Token login")

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

    def logout(self) -> None:
        """Tell the server the session is ending (cmd 2), then close the socket."""
        if self.session.is_open:
            try:
                self.request(CMD_LOGOUT, timeout=3)
            except Exception as e:
                log.debug("logout: %s", e)
        self.session.close()

    def reconnect(self, login_id: Optional[int] = None, password: Optional[str] = None) -> bool:
        """Try the preferred host, then each known host; log in if credentials are given."""
        self.logout()
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
        """Reconnect, re-login (token, then password), and restore symbols, trading state and subscriptions.

        Rate-limited by ``reconnect_min_interval``.
        """
        wait = self.reconnect_min_interval - (time.time() - self._last_reconnect)
        if wait > 0:
            log.info("reconnect rate-limited, waiting %.0fs", wait)
            time.sleep(wait)
        self._last_reconnect = time.time()
        self.logout()
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
