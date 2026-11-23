"""Encrypted request/response session with a frame queue shared between threads."""

import logging
import struct
import threading
import time
from typing import Optional

from ..constants.commands import CMD_HELLO
from ..constants.network import INITIAL_KEY, WS_PORT
from ..exceptions import ConnectionFailed
from ..models import Frame
from ..protocol import AesCipher, decode_frame, encode_frame
from .websocket import WebSocketTransport

log = logging.getLogger("mt5direct.transport")

_HELLO_PAYLOAD = b'\x00' * 64
_SESSION_KEY_SLICE = slice(66, 98)
_POLL = 0.1


class Session:
    """Owns the socket, the AES key, and a queue of frames not yet claimed by anyone.

    Two reading modes:

    * **Direct**: no background reader. ``recv`` and ``recv_any`` read the socket
      themselves. Frames that do not match a ``recv`` go to the queue.
    * **Reader-owned**: a background thread (the tick listener) called
      ``attach_reader`` and is the only one reading the socket. ``recv`` from other
      threads then waits on the queue, and ``recv_any`` on the reader thread hands
      replies for awaited commands to the queue instead of returning them. This is
      what lets a heartbeat ``ping`` or a ``buy`` run while the listener is active.
    """

    def __init__(self, host: str, port: int = WS_PORT, verify_ssl: bool = True):
        self.host, self.port = host, port
        self.verify_ssl = verify_ssl
        """Verify the server certificate (default). Disable only for brokers with self-signed certificates."""
        if ":" in host:
            self.address = host
        self.server_id = 0
        self.cipher = AesCipher(INITIAL_KEY)
        self._transport: Optional[WebSocketTransport] = None
        self._queue: list[Frame] = []
        self._cond = threading.Condition()
        self._waiting: dict[int, int] = {}
        self._reader: Optional[threading.Thread] = None

    @property
    def is_open(self) -> bool:
        return self._transport is not None and self._transport.is_open

    @property
    def address(self) -> str:
        """``host`` or ``host:port`` when the port is not the default."""
        return self.host if self.port == WS_PORT else f"{self.host}:{self.port}"

    @address.setter
    def address(self, value: str) -> None:
        host, _, port = value.partition(":")
        self.host, self.port = host, int(port) if port else WS_PORT

    # -- connection -------------------------------------------------------------

    def connect(self) -> None:
        """Open the socket and perform the hello handshake, switching to the session key."""
        self._transport = WebSocketTransport(self.host, self.port, verify_ssl=self.verify_ssl)
        self._transport.open(timeout=15)
        self.cipher = AesCipher(INITIAL_KEY)
        self.send(CMD_HELLO, _HELLO_PAYLOAD)
        resp = self.recv(CMD_HELLO)
        if resp is None or resp.status != 0:
            raise ConnectionFailed(f"Hello failed: {resp}")
        self.server_id = struct.unpack('<H', resp.payload[0:2])[0]
        self.cipher = AesCipher(resp.payload[_SESSION_KEY_SLICE])
        log.info("connected to %s (server %d)", self.address, self.server_id)

    def close(self) -> None:
        if self._transport:
            self._transport.close()
            self._transport = None
            log.debug("connection closed")

    def send(self, cmd: int, payload: bytes = b'') -> None:
        self._transport.send_binary(encode_frame(self.cipher, cmd, payload))

    def request(self, cmd: int, payload: bytes = b'', timeout: float = 15) -> Optional[Frame]:
        """Send ``cmd`` and return its reply.

        Frames with the same ``cmd`` already sitting in the queue were pushed by the
        server before this request and are discarded first, so the reply is never a
        stale snapshot (the server pushes cmd 4 position lists unprompted).
        """
        with self._cond:
            self._queue = [f for f in self._queue if f.cmd != cmd]
            if self._reader_elsewhere():
                self._waiting[cmd] = self._waiting.get(cmd, 0) + 1
                registered = True
            else:
                registered = False
        try:
            self.send(cmd, payload)
            if registered:
                with self._cond:
                    self._waiting[cmd] -= 1          # _wait_for re-registers
                    registered = False
                    return self._wait_for(cmd, timeout)
            return self.recv(cmd, timeout)
        finally:
            if registered:
                with self._cond:
                    self._waiting[cmd] -= 1
                    if self._waiting[cmd] <= 0:
                        del self._waiting[cmd]

    # -- reader ownership -----------------------------------------------------------

    def attach_reader(self, thread: threading.Thread) -> None:
        """Declare ``thread`` the sole socket reader (it must loop on ``recv_any``)."""
        with self._cond:
            self._reader = thread

    def detach_reader(self) -> None:
        with self._cond:
            self._reader = None
            self._cond.notify_all()

    def _reader_elsewhere(self) -> bool:
        return self._reader is not None and self._reader is not threading.current_thread() and self._reader.is_alive()

    # -- receiving ------------------------------------------------------------------

    def _recv_raw(self, timeout: float = 15) -> Optional[Frame]:
        return decode_frame(self.cipher, self._transport.recv(timeout))

    def _pop(self, cmd: int) -> Optional[Frame]:
        for i, f in enumerate(self._queue):
            if f.cmd == cmd:
                return self._queue.pop(i)
        return None

    def recv(self, expected_cmd: int, timeout: float = 15) -> Optional[Frame]:
        """Wait for a frame with ``expected_cmd``; other frames are queued for ``recv_any``."""
        with self._cond:
            f = self._pop(expected_cmd)
            if f:
                return f
            if self._reader_elsewhere():
                return self._wait_for(expected_cmd, timeout)
        deadline = time.time() + timeout
        while time.time() < deadline:
            try:
                msg = self._recv_raw(timeout=max(_POLL, deadline - time.time()))
            except Exception as e:
                log.debug("recv(%d) interrupted: %s", expected_cmd, e)
                break
            if msg is None:
                continue
            if msg.cmd == expected_cmd:
                return msg
            with self._cond:
                self._queue.append(msg)
                self._cond.notify_all()
        return None

    def _wait_for(self, cmd: int, timeout: float) -> Optional[Frame]:
        """Called with the lock held while a reader thread owns the socket."""
        self._waiting[cmd] = self._waiting.get(cmd, 0) + 1
        try:
            deadline = time.time() + timeout
            while True:
                f = self._pop(cmd)
                if f:
                    return f
                remaining = deadline - time.time()
                if remaining <= 0 or not self._reader_elsewhere():
                    return None
                self._cond.wait(remaining)
        finally:
            self._waiting[cmd] -= 1
            if self._waiting[cmd] <= 0:
                del self._waiting[cmd]

    def recv_any(self, timeout: float = 5) -> Optional[Frame]:
        """Next frame, queued or fresh; ``None`` on timeout or error.

        A fresh frame another thread is waiting on is also queued for that waiter.
        Queued frames reserved for waiters are skipped.
        """
        with self._cond:
            for i, f in enumerate(self._queue):
                if f.cmd not in self._waiting:
                    return self._queue.pop(i)
        deadline = time.time() + timeout
        while True:
            try:
                msg = self._recv_raw(timeout=max(_POLL, deadline - time.time()))
            except Exception as e:
                log.debug("recv_any: %s", e)
                return None
            if msg is None:
                if time.time() >= deadline:
                    return None
                continue
            with self._cond:
                if msg.cmd in self._waiting:
                    # hand a copy to the waiter; the reader still sees it so events keep firing
                    self._queue.append(msg)
                    self._cond.notify_all()
            return msg
