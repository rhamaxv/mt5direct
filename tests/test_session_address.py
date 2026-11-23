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


def test_tls_verification_default_and_opt_out():
    from mt5direct.transport import WebSocketTransport
    assert WebSocketTransport("h").verify_ssl is True
    assert Session("h").verify_ssl is True
    assert Session("h", verify_ssl=False).verify_ssl is False
