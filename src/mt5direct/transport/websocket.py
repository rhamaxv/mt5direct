"""Thin wrapper around ``websocket-client`` for the binary terminal endpoint."""

import socket
import ssl
from typing import Optional

import websocket

from ..constants.network import WS_PATH, WS_PORT

_OPCODE_BINARY = 0x2


class WebSocketTransport:
    def __init__(self, host: str, port: int = WS_PORT, path: str = WS_PATH, verify_ssl: bool = True):
        self.host = host
        self.port = port
        self.path = path
        self.verify_ssl = verify_ssl
        self.cookie: Optional[str] = None
        """``wt_dtoken=...`` set by the server on the upgrade response; forwarded on later connections."""
        self._ws = None

    @property
    def url(self) -> str:
        return f'wss://{self.host}:{self.port}{self.path}'

    @property
    def is_open(self) -> bool:
        return self._ws is not None

    def open(self, timeout: float = 15, cookie: Optional[str] = None) -> None:
        """Connect, sending ``cookie`` if given, and capture the server's ``wt_dtoken`` cookie."""
        sslopt = {'cert_reqs': ssl.CERT_REQUIRED} if self.verify_ssl else {'cert_reqs': ssl.CERT_NONE, 'check_hostname': False}
        self._ws = websocket.WebSocket(sslopt=sslopt)
        kwargs = {'timeout': timeout}
        if cookie:
            kwargs['cookie'] = cookie
        self._ws.connect(self.url, **kwargs)
        enable_keepalive(self._ws.sock)
        self.cookie = parse_dtoken_cookie(self._ws.getheaders()) or cookie

    def send_binary(self, data: bytes) -> None:
        self._ws.send(data, opcode=_OPCODE_BINARY)

    def recv(self, timeout: float) -> bytes:
        self._ws.settimeout(timeout)
        _opcode, data = self._ws.recv_data()
        return bytes(data)

    def close(self) -> None:
        ws, self._ws = self._ws, None
        if ws:
            for fn in (ws.close, ws.shutdown):
                try:
                    fn()
                except Exception:
                    pass


def parse_dtoken_cookie(headers) -> Optional[str]:
    """``wt_dtoken=...`` from an upgrade response's ``Set-Cookie`` header, without attributes."""
    if not headers:
        return None
    for key, value in headers.items():
        if key.lower() == 'set-cookie' and 'wt_dtoken=' in value:
            return value.split(';', 1)[0].strip()
    return None


KEEPALIVE_IDLE = 15
KEEPALIVE_INTERVAL = 5
KEEPALIVE_COUNT = 3


def enable_keepalive(sock) -> None:
    """TCP keepalive so a silently dead peer is noticed within ~30 s even with no traffic."""
    if sock is None:
        return
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        idle_opt = getattr(socket, 'TCP_KEEPIDLE', None) or getattr(socket, 'TCP_KEEPALIVE', None)
        if idle_opt is not None:
            sock.setsockopt(socket.IPPROTO_TCP, idle_opt, KEEPALIVE_IDLE)
        if hasattr(socket, 'TCP_KEEPINTVL'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPINTVL, KEEPALIVE_INTERVAL)
        if hasattr(socket, 'TCP_KEEPCNT'):
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_KEEPCNT, KEEPALIVE_COUNT)
    except OSError:
        pass
