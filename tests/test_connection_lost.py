import threading
import time

import pytest
import websocket

from mt5direct.exceptions import ConnectionLost
from mt5direct.protocol import AesCipher
from mt5direct.transport import Session

KEY = bytes(range(32))


class DyingTransport:
    is_open = True

    def __init__(self, exc):
        self.exc = exc

    def recv(self, timeout):
        raise self.exc

    def send_binary(self, data):
        pass

    def close(self):
        self.is_open = False


def _session(exc):
    s = Session("fake")
    s.cipher = AesCipher(KEY)
    s._transport = DyingTransport(exc)
    return s


def test_timeout_is_not_a_loss():
    s = _session(websocket.WebSocketTimeoutException("timed out"))
    assert s.recv_any(timeout=0.2) is None
    assert s.is_open


@pytest.mark.parametrize("exc", [websocket.WebSocketConnectionClosedException("closed"),
                                 ConnectionResetError(54, "reset"), OSError(22, "Invalid argument")])
def test_dead_socket_raises_connection_lost_and_closes(exc):
    s = _session(exc)
    with pytest.raises(ConnectionLost):
        s.recv_any(timeout=1)
    assert not s.is_open


def test_recv_returns_none_on_loss():
    s = _session(websocket.WebSocketConnectionClosedException("closed"))
    assert s.recv(51, timeout=1) is None
    assert not s.is_open


def test_listener_reconnects_immediately_on_loss(monkeypatch):
    from mt5direct.services.base import ClientState
    from mt5direct.services.market_data import MarketDataService

    s = _session(websocket.WebSocketConnectionClosedException("closed"))
    calls, stop = [], threading.Event()

    class FakeAuth:
        def auto_reconnect(self):
            calls.append(time.time())
            if len(calls) >= 2:
                stop.set()
            return False

    m = MarketDataService(s, ClientState(), FakeAuth())
    t = m.start_tick_listener()
    stop.wait(5)
    m.stop_tick_listener(); t.join(3)
    assert len(calls) >= 2
    assert calls[1] - calls[0] < 3   # no 60 s wait


def test_auto_reconnect_backoff_doubles_and_resets(monkeypatch):
    from mt5direct.services.auth import AuthService
    from mt5direct.services.base import ClientState

    sleeps = []
    monkeypatch.setattr("mt5direct.services.auth.time.sleep", lambda d: sleeps.append(d))
    s = Session("fake")
    auth = AuthService(s, ClientState(), symbols=None, account=None)
    auth._reconnect_hosts = lambda: ["h1"]
    monkeypatch.setattr(s, "connect", lambda: (_ for _ in ()).throw(OSError("down")))
    for _ in range(6):
        assert auth.auto_reconnect() is False
    assert sleeps == [1, 2, 4, 8, 16, 30]
    assert auth._backoff == 30
    monkeypatch.setattr(s, "connect", lambda: None)
    auth.relogin = lambda: None
    for name in ("get_symbol_types", "get_symbols", "subscribe_all"):
        pass
    auth._symbols = type("S", (), {"get_symbol_types": lambda self: None, "get_symbols": lambda self: None,
                                   "subscribe_all": lambda self: None})()
    auth._account = type("A", (), {"init_trading": lambda self: None})()
    assert auth.auto_reconnect() is True
    assert auth._backoff == 1.0
