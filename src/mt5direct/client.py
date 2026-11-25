"""Facade that wires the session and services behind one object."""

from pathlib import Path
from typing import Optional, Union

from .constants.network import TRADE_HOSTS
from .discovery import Endpoint, resolve_server
from .sessions import SavedSession, default_session_path, read_session, write_session
from .models import Frame, Symbol
from .services import (
    AccountService, AuthService, ClientState, MarketDataService, PositionService,
    SymbolService, TradingService,
)
from .transport import Session


class MT5Client:
    """Standalone MT5 client.

    Domain operations live on ``auth``, ``account``, ``symbols``, ``market``, ``trading``
    and ``positions``; the flat methods below delegate to them for convenience.

    Pass ``server`` (a trade server name such as ``'Exness-MT5Trial6'``, see
    ``list_servers``) to look the host up, or ``host`` (``'host'`` or ``'host:port'``)
    to connect to a web terminal host directly. TLS certificates are verified unless
    ``verify_ssl=False``.
    """

    def __init__(self, host: Optional[str] = None, server: Optional[str] = None, verify_ssl: bool = True):
        self.endpoint: Optional[Endpoint] = None
        if server and not host:
            self.endpoint = resolve_server(server)
            host = self.endpoint.address
        self.session = Session(host or TRADE_HOSTS[0], verify_ssl=verify_ssl)
        self.state = ClientState()
        if self.endpoint:
            self.state.preferred_hosts = [self.endpoint.address]
        self.account = AccountService(self.session, self.state)
        self.symbols = SymbolService(self.session, self.state)
        self.auth = AuthService(self.session, self.state, self.symbols, self.account)
        self.market = MarketDataService(self.session, self.state, self.auth)
        self.trading = TradingService(self.session, self.state)
        self.positions = PositionService(self.session, self.state, self.trading, self.market)

    @classmethod
    def from_server(cls, server: str, verify_ssl: bool = True) -> "MT5Client":
        """Build a client for a trade server name, e.g. ``MT5Client.from_server('Exness-MT5Trial6')``."""
        return cls(server=server, verify_ssl=verify_ssl)

    # -- persistent sessions ----------------------------------------------

    def save_session(self, path: Optional[Union[str, Path]] = None) -> Path:
        """Write the token, device id and cookie of the current login to disk (never the password).

        Default location: ``~/.cache/mt5direct/sessions/<login>@<server>.json``, mode 0600.
        """
        st = self.state
        if not st.login_id or not st.login_token:
            raise ValueError("Not logged in; nothing to save.")
        saved = SavedSession(login=st.login_id, token=st.login_token, um=st.login_um,
                             device_hash=st.device_hash, cookie=self.session.cookie,
                             server=self.endpoint.server if self.endpoint else None,
                             host=None if self.endpoint else self.address)
        return write_session(saved, Path(path) if path else None)

    @classmethod
    def resume(cls, path: Optional[Union[str, Path]] = None, login: Optional[int] = None,
               server: Optional[str] = None, verify_ssl: bool = True) -> "MT5Client":
        """Connect and log in from a saved session, without a password.

        Give ``path`` or the ``login``/``server`` pair used when saving. Raises
        ``LoginFailed`` if the server no longer accepts the token; log in with the
        password once and call ``save_session`` again. The refreshed token is saved back.
        """
        if path is None:
            if login is None:
                raise ValueError("resume() needs path or login (and server).")
            path = default_session_path(login, server, None)
        saved = read_session(Path(path))
        client = cls(server=saved.server, host=saved.host, verify_ssl=verify_ssl)
        client.state.device_hash = saved.device_hash
        client.session.cookie = saved.cookie
        client.connect()
        client.auth.login_with_token(saved.login, saved.token, saved.um)
        client.save_session(path)
        return client

    # -- connection -------------------------------------------------------

    @property
    def host(self) -> str:
        return self.session.host

    @host.setter
    def host(self, value: str) -> None:
        self.session.address = value

    @property
    def address(self) -> str:
        return self.session.address

    @property
    def server_id(self) -> int:
        return self.session.server_id

    def connect(self) -> None:
        self.session.connect()

    def close(self) -> None:
        """Stop the listener and heartbeat threads, tell the server goodbye, close the socket."""
        self.market.stop()
        self.auth.logout()

    def recv_any(self, timeout: float = 5) -> Optional[Frame]:
        return self.session.recv_any(timeout=timeout)

    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    # -- symbol tables ----------------------------------------------------

    @property
    def symbol_list(self) -> list[Symbol]:
        return self.state.symbols

    @property
    def symbol_map(self) -> dict[str, Symbol]:
        return self.state.symbol_map

    @property
    def ta_to_sym(self) -> dict[int, Symbol]:
        return self.state.ta_to_sym

    # -- auth -------------------------------------------------------------

    def login(self, login_id: int, password: str):
        return self.auth.login(login_id, password)

    def login_with_token(self, login_id: int, token=None, um=None):
        return self.auth.login_with_token(login_id, token, um)

    def logout(self):
        return self.auth.logout()

    def ping(self):
        return self.auth.ping()

    def reconnect(self, login_id=None, password=None):
        return self.auth.reconnect(login_id, password)

    def auto_reconnect(self):
        return self.auth.auto_reconnect()

    # -- account ----------------------------------------------------------

    def get_account_info(self):
        return self.account.get_account_info()

    def get_account_summary(self):
        return self.account.get_account_summary()

    def init_trading(self):
        return self.account.init_trading()

    def get_history(self, from_ts=0, to_ts=0):
        return self.account.get_history(from_ts, to_ts)

    # -- symbols ----------------------------------------------------------

    def get_symbol_types(self):
        return self.symbols.get_symbol_types()

    def get_symbols(self):
        return self.symbols.get_symbols()

    def resolve_symbols(self, ta_list):
        return self.symbols.resolve_symbols(ta_list)

    def get_symbol_info(self, *names):
        return self.symbols.get_symbol_info(*names)

    def subscribe(self, ta_values):
        return self.symbols.subscribe(ta_values)

    def subscribe_by_name(self, *names):
        return self.symbols.subscribe_by_name(*names)

    def subscribe_all(self):
        return self.symbols.subscribe_all()

    def parse_trade_sessions(self, resolve_data):
        return self.symbols.parse_trade_sessions(resolve_data)

    def parse_trade_modes(self, resolve_data):
        return self.symbols.parse_trade_modes(resolve_data)

    def find_resolve_bid_offset(self, resolve_data, sym_name, expected_price, digits, tolerance=0.02):
        return self.symbols.find_resolve_bid_offset(resolve_data, sym_name, expected_price, digits, tolerance)

    def extract_resolve_prices(self, resolve_data, bid_offset):
        return self.symbols.extract_resolve_prices(resolve_data, bid_offset)

    # -- market data ------------------------------------------------------

    def get_candles(self, symbol, timeframe='H1', count=1000, from_ts=None, to_ts=None):
        return self.market.get_candles(symbol, timeframe, count, from_ts, to_ts)

    def parse_tick(self, data, offset=0):
        return self.market.parse_tick(data, offset)

    def get_candles_df(self, symbol, timeframe='H1', count=1000, **kwargs):
        return self.market.get_candles_df(symbol, timeframe, count, **kwargs)

    def on_tick(self, callback):
        return self.market.on_tick(callback)

    def on_trade(self, callback):
        return self.market.on_trade(callback)

    def on_position_change(self, callback):
        return self.market.on_position_change(callback)

    def on_transaction(self, callback):
        return self.market.on_transaction(callback)

    def start_heartbeat(self, interval=30):
        return self.market.start_heartbeat(interval)

    def stop_heartbeat(self):
        return self.market.stop_heartbeat()

    def start_tick_listener(self, symbols=None):
        return self.market.start_tick_listener(symbols)

    def stop_tick_listener(self):
        return self.market.stop_tick_listener()

    # -- trading ----------------------------------------------------------

    def trade(self, *args, **kwargs):
        return self.trading.trade(*args, **kwargs)

    def wait_trade_result(self, timeout=30):
        return self.trading.wait_trade_result(timeout)

    def buy(self, symbol, lots, sl=0.0, tp=0.0, comment=""):
        return self.trading.buy(symbol, lots, sl, tp, comment)

    def sell(self, symbol, lots, sl=0.0, tp=0.0, comment=""):
        return self.trading.sell(symbol, lots, sl, tp, comment)

    def buy_limit(self, symbol, lots, price, sl=0.0, tp=0.0, comment=""):
        return self.trading.buy_limit(symbol, lots, price, sl, tp, comment)

    def sell_limit(self, symbol, lots, price, sl=0.0, tp=0.0, comment=""):
        return self.trading.sell_limit(symbol, lots, price, sl, tp, comment)

    def buy_stop(self, symbol, lots, price, sl=0.0, tp=0.0, comment=""):
        return self.trading.buy_stop(symbol, lots, price, sl, tp, comment)

    def sell_stop(self, symbol, lots, price, sl=0.0, tp=0.0, comment=""):
        return self.trading.sell_stop(symbol, lots, price, sl, tp, comment)

    def modify_sl_tp(self, symbol, position_ticket, sl=0.0, tp=0.0):
        return self.trading.modify_sl_tp(symbol, position_ticket, sl, tp)

    def modify_pending(self, symbol, order_ticket, price, sl=0.0, tp=0.0):
        return self.trading.modify_pending(symbol, order_ticket, price, sl, tp)

    def cancel_order(self, symbol, order_ticket):
        return self.trading.cancel_order(symbol, order_ticket)

    def close_position(self, symbol, ticket, lots=None, pos_type='BUY'):
        return self.trading.close_position(symbol, ticket, lots, pos_type)

    def close_by_order(self, symbol, order_ticket, lots, pos_type='BUY'):
        return self.trading.close_by_order(symbol, order_ticket, lots, pos_type)

    # -- positions --------------------------------------------------------

    def get_positions(self):
        return self.positions.get_positions()

    def get_pending_orders(self):
        return self.positions.get_pending_orders()

    def get_positions_and_orders(self):
        return self.positions.get_positions_and_orders()

    def refresh_positions(self):
        return self.positions.refresh()

    @property
    def book(self):
        """Live position/pending-order book (``positions``, ``pending``, ``balance``)."""
        return self.state.book

    def close_all(self, symbol=None):
        return self.positions.close_all(symbol)

    def track_positions(self, duration=60, callback=None):
        return self.positions.track_positions(duration, callback)
