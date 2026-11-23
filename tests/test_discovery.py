import json

import pytest

from mt5direct.discovery import (
    Endpoint, Registry, candidate_addresses, discover_from_url, inspect_host, list_servers,
    load_registry, parse_terminal_params, resolve_server, split_address, split_server_name,
)
from mt5direct.exceptions import ServerNotFound


@pytest.fixture(autouse=True)
def isolated_cache(tmp_path, monkeypatch):
    monkeypatch.setenv("MT5DIRECT_CACHE_DIR", str(tmp_path))
    monkeypatch.setenv("MT5DIRECT_OFFLINE", "1")


def _page(server, broker="Exness Technologies Ltd", build=6230):
    params = {"build": build, "broker": {"name": broker},
              "servers": [{"server": server, "type": "demo"}], "internal": True}
    return f'<html><script>window.__terminal_params = {json.dumps(params)};</script></html>'


def _registry():
    return Registry(
        servers={"FinexBisnisSolusi-Real": "real-terminal.finex.co.id",
                 "HFMarketsGlobal-Live3": "live3.webterminal-hfm.com:1951"},
        patterns={"Exness": {"host": "{code}.exwebterm.com", "port": 443}},
    )


def test_split_helpers():
    assert split_server_name("Exness-MT5Trial6") == ("Exness", "MT5Trial6")
    assert split_server_name("NoDash") == ("NoDash", "")
    assert split_address("host") == ("host", 443)
    assert split_address("host:1951") == ("host", 1951)


def test_endpoint_address():
    assert Endpoint(host="a", server="s").address == "a"
    assert Endpoint(host="a", server="s", port=1951).address == "a:1951"


def test_candidates_registry_then_pattern_then_guesses():
    assert candidate_addresses("HFMarketsGlobal-Live3", _registry())[0] == "live3.webterminal-hfm.com:1951"
    assert candidate_addresses("Exness-MT5Trial6", _registry()) == [
        "mt5trial6.exwebterm.com", "mt5trial6.exnesswebterm.com", "mt5trial6.webterminal-exness.com"]
    assert candidate_addresses("Weird", _registry()) == []


def test_bundled_registry_has_verified_entries():
    reg = load_registry(remote=False)
    assert reg.servers["FinexBisnisSolusi-Real"] == "real-terminal.finex.co.id"
    assert reg.servers["HFMarketsGlobal-Live1"] == "live.webterminal-hfm.com:1951"
    assert reg.patterns["Exness"]["host"] == "{code}.exwebterm.com"


def test_parse_terminal_params():
    assert parse_terminal_params(_page("X-Y"))["servers"][0]["server"] == "X-Y"
    assert parse_terminal_params("<html>nothing</html>") is None
    assert parse_terminal_params("<script>window.__terminal_params = {bad;</script>") is None


def test_inspect_host_uses_port():
    seen = []

    def fetch(url, t):
        seen.append(url)
        return _page("HFMarketsGlobal-Live3", broker="HF Markets", build=6140)

    eps = inspect_host("live3.webterminal-hfm.com", 1951, fetch=fetch)
    assert seen == ["https://live3.webterminal-hfm.com:1951/terminal"]
    assert eps == [Endpoint(host="live3.webterminal-hfm.com", port=1951, server="HFMarketsGlobal-Live3",
                            broker="HF Markets", build=6140)]


def test_inspect_host_unreachable_is_empty():
    def boom(url, t):
        raise OSError("down")
    assert inspect_host("x.example", fetch=boom) == []


def test_resolve_from_registry_with_port():
    fetch = lambda url, t: _page("HFMarketsGlobal-Live3") if ":1951/terminal" in url else "<html></html>"
    ep = resolve_server("HFMarketsGlobal-Live3", registry=_registry(), fetch=fetch)
    assert ep.address == "live3.webterminal-hfm.com:1951"


def test_resolve_from_pattern_and_remember(tmp_path):
    fetch = lambda url, t: _page("Exness-MT5Trial6") if "mt5trial6.exwebterm.com" in url else "<html></html>"
    ep = resolve_server("Exness-MT5Trial6", registry=_registry(), fetch=fetch)
    assert ep.host == "mt5trial6.exwebterm.com"
    learned = json.loads((tmp_path / "learned.json").read_text())
    assert learned["servers"]["Exness-MT5Trial6"] == "mt5trial6.exwebterm.com"
    # next load picks it up as an exact entry
    assert load_registry(remote=False).servers["Exness-MT5Trial6"] == "mt5trial6.exwebterm.com"


def test_resolve_rejects_wrong_announcement():
    fetch = lambda url, t: _page("Exness-MT5Trial")  # host serves a different server
    with pytest.raises(ServerNotFound) as e:
        resolve_server("Exness-MT5Trial6", registry=_registry(), fetch=fetch)
    assert "mt5trial6.exwebterm.com" in str(e.value)
    assert "discover_from_url" in str(e.value)


def test_discover_from_launcher_page(tmp_path):
    launcher = ('<html><iframe src="https://live.webterminal-hfm.com:1951/terminal?theme=blueRed&amp;lang=en">'
                '</iframe><a href="https://demo-4.webterminal-hfm.com:1951/terminal">demo</a></html>')

    def fetch(url, t):
        if url == "https://webterminal.hfm.com/en/mt5":
            return launcher
        if "live.webterminal-hfm.com:1951/terminal" in url:
            return _page("HFMarketsGlobal-Live1", broker="HF Markets", build=6140)
        if "demo-4.webterminal-hfm.com:1951/terminal" in url:
            return _page("HFMarketsGlobal-Demo4", broker="HF Markets", build=6140)
        raise OSError("unreachable")

    eps = discover_from_url("https://webterminal.hfm.com/en/mt5", fetch=fetch)
    assert [e.server for e in eps] == ["HFMarketsGlobal-Live1", "HFMarketsGlobal-Demo4"]
    assert load_registry(remote=False).servers["HFMarketsGlobal-Demo4"] == "demo-4.webterminal-hfm.com:1951"


def test_discover_from_terminal_page_itself():
    fetch = lambda url, t: _page("FinexBisnisSolusi-Real", broker="Finex")
    eps = discover_from_url("https://real-terminal.finex.co.id/terminal", fetch=fetch)
    assert eps[0].address == "real-terminal.finex.co.id"


def test_list_servers_filters():
    payload = json.dumps({"mt5": ["Exness-MT5Trial6", "FinexBisnisSolusi-Real", "Exness-MT5Real"]})
    assert list_servers("finex", fetch=lambda u, t: payload) == ["FinexBisnisSolusi-Real"]
    assert len(list_servers(fetch=lambda u, t: payload)) == 3
