import socket
import time

import pytest
import websocket

from mt5direct.models import Frame
from mt5direct.protocol import AesCipher, encode_frame
from mt5direct.transport import Session
from mt5direct.transport.websocket import enable_keepalive

KEY = bytes(range(32))


class FeedTransport:
    is_open = True

    def __init__(self, cipher, frames):
        self.cipher, self.frames = cipher, list(frames)

    def recv(self, timeout):
        if self.frames:
            cmd, payload = self.frames.pop(0)
            return encode_frame(self.cipher, cmd, payload)
        raise websocket.WebSocketTimeoutException()

    def send_binary(self, data): pass
    def close(self): self.is_open = False


def _session(frames):
    s = Session("fake"); s.cipher = AesCipher(KEY); s._transport = FeedTransport(s.cipher, frames); return s


def test_queue_is_capped_but_keeps_awaited_frames():
    s = _session([(8, b'\x00t')] * 50 + [(51, b'\x00pong')])
    s.queue_limit = 10
    with s._cond:
        s._waiting[19] = 1
        s._queue = [Frame(19, 0, b'keep')]
    # recv(3) drains everything else into the queue, overflowing it
    assert s.recv(3, timeout=0.5) is None
    assert len(s._queue) <= 11
    assert Frame(19, 0, b'keep') in s._queue


def test_drop_and_clear():
    s = _session([])
    s._queue = [Frame(19, 0, b'old'), Frame(8, 0, b't'), Frame(12, 0, b'ack')]
    assert s.drop(12, 19) == 2
    assert [f.cmd for f in s._queue] == [8]
    s.clear(); assert s._queue == []


def test_last_recv_at_updates():
    s = _session([(8, b'\x00t')])
    assert s.last_recv_at == 0.0
    s.recv_any(timeout=0.2)
    assert time.time() - s.last_recv_at < 1


def test_enable_keepalive_sets_options():
    srv = socket.socket(); srv.bind(("127.0.0.1", 0)); srv.listen(1)
    cli = socket.create_connection(srv.getsockname())
    try:
        enable_keepalive(cli)
        assert cli.getsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE) != 0
        idle_opt = getattr(socket, 'TCP_KEEPIDLE', None) or getattr(socket, 'TCP_KEEPALIVE', None)
        if idle_opt is not None:
            assert cli.getsockopt(socket.IPPROTO_TCP, idle_opt) == 15
    finally:
        cli.close(); srv.close()
    enable_keepalive(None)   # no-op


def test_connection_state_callbacks():
    from mt5direct import MT5Client
    c = MT5Client(host="h.example")
    seen = []
    c.on_connection_change(seen.append)
    assert c.connection_state == "disconnected" and not c.is_connected
    c.state.set_connection_state("connecting"); c.state.set_connection_state("connecting")
    c.state.set_connection_state("connected")
    assert seen == ["connecting", "connected"]


def test_trade_drops_stale_results(monkeypatch):
    from mt5direct.services.base import ClientState
    from mt5direct.services.trading import TradingService
    s = _session([])
    s._queue = [Frame(19, 0, b'stale'), Frame(8, 0, b'tick')]
    t = TradingService(s, ClientState())
    monkeypatch.setattr(t, "request", lambda *a, **k: None)
    t.trade(0, "EURUSD", 0.01)
    assert [f.cmd for f in s._queue] == [8]


def test_auto_reconnect_never_reports_disconnected_mid_cycle(monkeypatch):
    from mt5direct.services.auth import AuthService
    from mt5direct.services.base import ClientState
    monkeypatch.setattr("mt5direct.services.auth.time.sleep", lambda d: None)
    s = Session("fake"); st = ClientState(); st.connection_state = "connected"
    seen = []; st.connection_callbacks.append(seen.append)
    auth = AuthService(s, st, symbols=None, account=None)
    auth._reconnect_hosts = lambda: ["h1"]
    monkeypatch.setattr(s, "connect", lambda: None)
    auth.relogin = lambda: None
    auth._symbols = type("S", (), {"get_symbol_types": lambda self: None, "get_symbols": lambda self: None,
                                   "subscribe_all": lambda self: None})()
    auth._account = type("A", (), {"init_trading": lambda self: None})()
    assert auth.auto_reconnect() is True
    assert seen == ["reconnecting", "connected"]
    monkeypatch.setattr(s, "connect", lambda: (_ for _ in ()).throw(OSError("down")))
    seen.clear()
    assert auth.auto_reconnect() is False
    assert seen == ["reconnecting", "disconnected"]
