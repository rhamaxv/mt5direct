"""Encrypted request/response session with out-of-order message buffering."""

import struct
import threading
import time
from typing import Optional

from ..constants.commands import CMD_HELLO
from ..constants.network import INITIAL_KEY
from ..exceptions import ConnectionFailed
from ..models import Frame
from ..protocol import AesCipher, decode_frame, encode_frame
from .websocket import WebSocketTransport

_HELLO_PAYLOAD = b'\x00' * 64
_SESSION_KEY_SLICE = slice(66, 98)


class Session:
    """Owns the socket, the AES key, and a queue of frames received while waiting for others."""

    def __init__(self, host: str):
        self.host = host
        self.server_id = 0
        self.cipher = AesCipher(INITIAL_KEY)
        self._transport: Optional[WebSocketTransport] = None
        self._queue: list[Frame] = []
        self._lock = threading.Lock()

    @property
    def is_open(self) -> bool:
        return self._transport is not None and self._transport.is_open

    def connect(self) -> None:
        """Open the socket and perform the hello handshake, switching to the session key."""
        self._transport = WebSocketTransport(self.host)
        self._transport.open(timeout=15)
        self.cipher = AesCipher(INITIAL_KEY)
        self.send(CMD_HELLO, _HELLO_PAYLOAD)
        resp = self.recv(CMD_HELLO)
        if resp is None or resp.status != 0:
            raise ConnectionFailed(f"Hello failed: {resp}")
        self.server_id = struct.unpack('<H', resp.payload[0:2])[0]
        self.cipher = AesCipher(resp.payload[_SESSION_KEY_SLICE])

    def send(self, cmd: int, payload: bytes = b'') -> None:
        self._transport.send_binary(encode_frame(self.cipher, cmd, payload))

    def _recv_raw(self, timeout: float = 15) -> Optional[Frame]:
        return decode_frame(self.cipher, self._transport.recv(timeout))

    def recv(self, expected_cmd: int, timeout: float = 15) -> Optional[Frame]:
        """Wait for a frame with ``expected_cmd``; other frames are queued for ``recv_any``."""
        with self._lock:
            for i, queued in enumerate(self._queue):
                if queued.cmd == expected_cmd:
                    self._queue.pop(i)
                    return queued
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = self._recv_raw(timeout=max(0.1, deadline - time.time()))
            except Exception:
                break
            if msg is None:
                continue
            if msg.cmd == expected_cmd:
                return msg
            with self._lock:
                self._queue.append(msg)
        return None

    def recv_any(self, timeout: float = 5) -> Optional[Frame]:
        """Return the next frame, queued or fresh; ``None`` on timeout or error."""
        with self._lock:
            if self._queue:
                return self._queue.pop(0)
        try:
            return self._recv_raw(timeout=timeout)
        except Exception:
            return None

    def close(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None
