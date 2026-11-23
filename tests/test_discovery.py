import json

import pytest

from mt5direct.discovery import (
    Endpoint, candidate_hosts, inspect_host, list_servers, parse_terminal_params, resolve_server,
    split_server_name,
)
from mt5direct.exceptions import ServerNotFound


def _page(server, broker="Exness Technologies Ltd", build=6230):
    params = {"build": build, "broker": {"name": broker},
              "servers": [{"server": server, "type": "demo"}], "internal": True}
    return f'<html><script>window.__terminal_params = {json.dumps(params)};</script></html>'


def test_split_server_name():
    assert split_server_name("Exness-MT5Trial6") == ("Exness", "MT5Trial6")
    assert split_server_name("NoDash") == ("NoDash", "")


def test_candidate_hosts_known_broker_first():
    assert candidate_hosts("Exness-MT5Trial6") == [
        "mt5trial6.exwebterm.com", "mt5trial6.exnesswebterm.com"]


def test_candidate_hosts_known_server():
    assert candidate_hosts("MetaQuotes-Demo")[0] == "web.metatrader.app"


def test_candidate_hosts_no_dash():
    assert candidate_hosts("Weird") == []


def test_parse_terminal_params():
    p = parse_terminal_params(_page("Exness-MT5Real8"))
    assert p["servers"][0]["server"] == "Exness-MT5Real8"
    assert parse_terminal_params("<html>nothing</html>") is None
    assert parse_terminal_params("<script>window.__terminal_params = {bad;</script>") is None


def test_inspect_host_parses_announcement():
    eps = inspect_host("x.example", fetch=lambda url, t: _page("Exness-MT5Trial6"))
    assert eps == [Endpoint(host="x.example", server="Exness-MT5Trial6",
                            broker="Exness Technologies Ltd", build=6230)]


def test_inspect_host_unreachable_is_empty():
    def boom(url, t):
        raise OSError("down")
    assert inspect_host("x.example", fetch=boom) == []


def test_resolve_server_verifies_announcement():
    seen = []

    def fetch(url, t):
        seen.append(url)
        if "mt5trial6.exwebterm.com" in url:
            return _page("Exness-MT5Trial6")
        raise OSError("unreachable")

    ep = resolve_server("Exness-MT5Trial6", fetch=fetch)
    assert ep.host == "mt5trial6.exwebterm.com"
    assert ep.path == "/terminal"
    assert seen == ["https://mt5trial6.exwebterm.com/terminal"]


def test_resolve_server_rejects_wrong_announcement():
    fetch = lambda url, t: _page("Exness-MT5Trial")  # host serves a different server
    with pytest.raises(ServerNotFound) as e:
        resolve_server("Exness-MT5Trial6", fetch=fetch)
    assert "mt5trial6.exwebterm.com" in str(e.value)


def test_resolve_server_unknown_broker():
    with pytest.raises(ServerNotFound):
        resolve_server("Nobody-Live", fetch=lambda u, t: "<html></html>")


def test_list_servers_filters():
    payload = json.dumps({"mt5": ["Exness-MT5Trial6", "ICMarketsSC-Demo", "Exness-MT5Real"]})
    assert list_servers("exness", fetch=lambda u, t: payload) == ["Exness-MT5Trial6", "Exness-MT5Real"]
    assert len(list_servers(fetch=lambda u, t: payload)) == 3
