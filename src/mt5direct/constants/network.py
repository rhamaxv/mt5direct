"""Connection endpoints and the bootstrap AES key used before the hello handshake."""

INITIAL_KEY = bytes.fromhex('02de02a1a65cc794684fcbea1ecb0fd74ae657e43662c11eee885d2fd64f4964')

TRADE_HOSTS = [
    "mt5trial6.exwebterm.com",
]
"""Fallback hosts for reconnects when no server was resolved. Hostnames only: bare IPs
cannot pass certificate verification."""

WS_PORT = 443
WS_PATH = "/terminal"
