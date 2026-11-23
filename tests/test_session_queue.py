"""Session queue behaviour with a fake transport and no sockets."""

import threading
import time

from mt5direct.models import Frame
from mt5direct.protocol import AesCipher, encode_frame
from mt5direct.transport import Session

KEY = bytes(range(32))


class FakeTransport:
    """Hands out pre-encoded frames; blocks (sleeps) when empty, raising TimeoutError."""

    def __init__(self, cipher, frames):
        self.cipher = cipher
        self.frames = list(frames)
        self.lock = threading.Lock()
        self.is_open = True

    def recv(self, timeout):
        with self.lock:
            if self.frames:
                cmd, payload = self.frames.pop(0)
                return encode_frame(self.cipher, cmd, payload)
        time.sleep(min(timeout, 0.05))
        raise TimeoutError("no data")

    def send_binary(self, data):
        pass

    def close(self):
        self.is_open = False


def _session(frames):
    s = Session("fake")
    s.cipher = AesCipher(KEY)
    s._transport = FakeTransport(s.cipher, frames)
    return s


def test_recv_queues_unrelated_frames_for_recv_any():
    s = _session([(8, b'\x00tick'), (51, b'\x00pong')])
    assert s.recv(51, timeout=1) == Frame(51, 0, b'pong')
    assert s.recv_any(timeout=0.2) == Frame(8, 0, b'tick')
    assert s.recv_any(timeout=0.2) is None


def _start_reader(s, seen, stop):
    def listener():
        while not stop.is_set():
            f = s.recv_any(timeout=0.1)
            if f:
                seen.append(f)
    t = threading.Thread(target=listener, daemon=True)
    s.attach_reader(t)
    t.start()
    return t


def _wait_registered(s, cmd):
    for _ in range(50):
        with s._cond:
            if cmd in s._waiting:
                return
        time.sleep(0.01)
    raise AssertionError("waiter never registered")


def test_reader_thread_hands_replies_to_waiters():
    """A listener loop owns the socket; a ping from another thread still gets its reply."""
    s = _session([])
    seen, stop = [], threading.Event()
    t = _start_reader(s, seen, stop)
    result = {}
    waiter = threading.Thread(target=lambda: result.setdefault("pong", s.recv(51, timeout=2)), daemon=True)
    waiter.start()
    _wait_registered(s, 51)
    with s._transport.lock:
        s._transport.frames += [(8, b'\x00t1'), (51, b'\x00pong'), (8, b'\x00t2')]
    waiter.join(3)
    time.sleep(0.3)
    stop.set(); t.join(1); s.detach_reader()
    assert result["pong"] == Frame(51, 0, b'pong')
    assert [f.payload for f in seen] == [b't1', b'pong', b't2']   # the reader sees everything


def test_recv_times_out_when_reader_owns_socket_and_nothing_arrives():
    s = _session([])
    t = threading.Thread(target=lambda: time.sleep(0.5), daemon=True)
    t.start()
    s.attach_reader(t)
    t0 = time.time()
    assert s.recv(51, timeout=0.3) is None
    assert 0.25 <= time.time() - t0 < 1.0
    s.detach_reader()


def test_reader_sees_frame_that_is_also_handed_to_waiter():
    """Trade results must reach both wait_trade_result (waiter) and on_trade (listener)."""
    s = _session([])
    seen, stop = [], threading.Event()
    t = _start_reader(s, seen, stop)
    got = {}
    waiter = threading.Thread(target=lambda: got.setdefault("r", s.recv(19, timeout=2)), daemon=True)
    waiter.start()
    _wait_registered(s, 19)
    with s._transport.lock:
        s._transport.frames.append((19, b'\x00result'))
    waiter.join(3)
    time.sleep(0.3)
    stop.set(); t.join(1); s.detach_reader()
    assert got["r"] == Frame(19, 0, b'result')
    assert seen == [Frame(19, 0, b'result')]


def test_request_discards_stale_pushed_frames():
    """A cmd-4 list pushed before the request must not be returned as the reply."""
    s = _session([(4, b'\x00fresh')])
    s._queue.append(Frame(4, 0, b'stale'))
    assert s.request(4, b'', timeout=1) == Frame(4, 0, b'fresh')
    assert s._queue == []
