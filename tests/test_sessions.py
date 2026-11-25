import os
import stat

from mt5direct import MT5Client, SavedSession
from mt5direct.sessions import default_session_path, delete_session, read_session, write_session
from mt5direct.transport.websocket import parse_dtoken_cookie


def test_parse_dtoken_cookie():
    hdrs = {"Date": "x", "Set-Cookie": "wt_dtoken=AbC+/==; max-age=315360000; samesite=none; secure; httponly; path=/"}
    assert parse_dtoken_cookie(hdrs) == "wt_dtoken=AbC+/=="
    assert parse_dtoken_cookie({"Set-Cookie": "other=1"}) is None
    assert parse_dtoken_cookie(None) is None


def test_session_roundtrip_and_permissions(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5DIRECT_CACHE_DIR", str(tmp_path))
    s = SavedSession(login=123, token=b'\x01' * 160, um=42, device_hash=b'\x02' * 16,
                     cookie="wt_dtoken=abc", server="Exness-MT5Trial6")
    path = write_session(s)
    assert path == default_session_path(123, "Exness-MT5Trial6", None)
    assert stat.S_IMODE(os.stat(path).st_mode) == 0o600
    assert read_session(path) == s
    assert "password" not in path.read_text()
    delete_session(path); delete_session(path)
    assert not path.exists()


def test_save_session_requires_login(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5DIRECT_CACHE_DIR", str(tmp_path))
    c = MT5Client(host="h.example")
    try:
        c.save_session()
    except ValueError as e:
        assert "Not logged in" in str(e)
    else:
        raise AssertionError("expected ValueError")


def test_save_session_contents(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5DIRECT_CACHE_DIR", str(tmp_path))
    c = MT5Client(host="h.example:1951")
    c.state.login_id, c.state.login_token, c.state.login_um = 7, b'\x09' * 160, 5
    c.session.cookie = "wt_dtoken=zzz"
    path = c.save_session()
    s = read_session(path)
    assert (s.login, s.um, s.cookie, s.host, s.server) == (7, 5, "wt_dtoken=zzz", "h.example:1951", None)
    assert s.device_hash == c.state.device_hash and len(s.device_hash) == 16
