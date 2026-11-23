from mt5direct.transport import Session


def test_session_default_port():
    s = Session("host.example")
    assert (s.host, s.port, s.address) == ("host.example", 443, "host.example")


def test_session_parses_port_from_address():
    s = Session("live3.webterminal-hfm.com:1951")
    assert (s.host, s.port) == ("live3.webterminal-hfm.com", 1951)
    assert s.address == "live3.webterminal-hfm.com:1951"
    s.address = "other.example"
    assert (s.host, s.port) == ("other.example", 443)
