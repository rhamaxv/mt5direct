"""Exception hierarchy for mt5direct."""


class MT5Error(Exception):
    """Base class for all mt5direct errors."""


class ConnectionFailed(MT5Error, ConnectionError):
    """Hello handshake with the trade server failed."""


class LoginFailed(MT5Error, ConnectionError):
    """Server rejected the login request."""


class ServerNotFound(MT5Error):
    """No web terminal host could be found or verified for a trade server name."""
