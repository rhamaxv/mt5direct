"""Connection endpoints and the bootstrap AES key used before the hello handshake."""

INITIAL_KEY = bytes.fromhex('02de02a1a65cc794684fcbea1ecb0fd74ae657e43662c11eee885d2fd64f4964')

TRADE_HOSTS = [
    "mt5trial6.exwebterm.com",
    "8.219.172.6", "47.236.224.248", "16.79.3.122",
    "47.130.41.116", "57.182.183.85", "18.61.99.175",
]

WS_PORT = 443
WS_PATH = "/terminal"
