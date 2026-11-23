"""Thin wrapper around ``websocket-client`` for the binary terminal endpoint."""

import ssl

import websocket

from ..constants.network import WS_PATH, WS_PORT

_OPCODE_BINARY = 0x2


class WebSocketTransport:
    def __init__(self, host: str, port: int = WS_PORT, path: str = WS_PATH):
        self.host = host
        self.port = port
        self.path = path
        self._ws = None

    @property
    def url(self) -> str:
        return f'wss://{self.host}:{self.port}{self.path}'

    @property
    def is_open(self) -> bool:
        return self._ws is not None

    def open(self, timeout: float = 15) -> None:
        self._ws = websocket.WebSocket(sslopt={'cert_reqs': ssl.CERT_NONE})
        self._ws.connect(self.url, timeout=timeout)

    def send_binary(self, data: bytes) -> None:
        self._ws.send(data, opcode=_OPCODE_BINARY)

    def recv(self, timeout: float) -> bytes:
        self._ws.settimeout(timeout)
        _opcode, data = self._ws.recv_data()
        return bytes(data)

    def close(self) -> None:
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None
