"""asyncio facade: every blocking ``MT5Client`` call runs in a worker thread."""

import asyncio
import functools
from typing import Optional

from .client import MT5Client


class AsyncMT5Client:
    """``await``-able wrapper around ``MT5Client``.

    Blocking calls run via ``asyncio.to_thread``; callbacks and thread controls are
    plain methods. The wrapped client is available as ``.sync``.
    """

    def __init__(self, host: Optional[str] = None, server: Optional[str] = None, verify_ssl: bool = True):
        self.sync = MT5Client(host=host, server=server, verify_ssl=verify_ssl)

    @classmethod
    def from_server(cls, server: str, verify_ssl: bool = True) -> "AsyncMT5Client":
        return cls(server=server, verify_ssl=verify_ssl)

    async def _run(self, fn, *args, **kwargs):
        return await asyncio.to_thread(functools.partial(fn, *args, **kwargs))

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, *exc) -> None:
        self.close()

    # -- connection / auth
    async def connect(self): return await self._run(self.sync.connect)
    async def login(self, login_id, password): return await self._run(self.sync.login, login_id, password)
    async def login_with_token(self, login_id, token=None): return await self._run(self.sync.login_with_token, login_id, token)
    async def ping(self): return await self._run(self.sync.ping)
    async def reconnect(self, login_id=None, password=None): return await self._run(self.sync.reconnect, login_id, password)

    # -- account
    async def get_account_info(self): return await self._run(self.sync.get_account_info)
    async def get_account_summary(self): return await self._run(self.sync.get_account_summary)
    async def init_trading(self): return await self._run(self.sync.init_trading)
    async def get_history(self, from_ts=0, to_ts=0): return await self._run(self.sync.get_history, from_ts, to_ts)

    # -- symbols
    async def get_symbols(self): return await self._run(self.sync.get_symbols)
    async def get_symbol_types(self): return await self._run(self.sync.get_symbol_types)
    async def get_symbol_info(self, *names): return await self._run(self.sync.get_symbol_info, *names)
    async def subscribe_all(self): return await self._run(self.sync.subscribe_all)
    async def subscribe_by_name(self, *names): return await self._run(self.sync.subscribe_by_name, *names)

    # -- market data
    async def get_candles(self, symbol, timeframe='H1', count=1000, **kw): return await self._run(self.sync.get_candles, symbol, timeframe, count, **kw)
    async def get_candles_df(self, symbol, timeframe='H1', count=1000, **kw): return await self._run(self.sync.get_candles_df, symbol, timeframe, count, **kw)

    # -- trading
    async def trade(self, *args, **kw): return await self._run(self.sync.trade, *args, **kw)
    async def wait_trade_result(self, timeout=30): return await self._run(self.sync.wait_trade_result, timeout)
    async def buy(self, symbol, lots, **kw): return await self._run(self.sync.buy, symbol, lots, **kw)
    async def sell(self, symbol, lots, **kw): return await self._run(self.sync.sell, symbol, lots, **kw)
    async def buy_limit(self, symbol, lots, price, **kw): return await self._run(self.sync.buy_limit, symbol, lots, price, **kw)
    async def sell_limit(self, symbol, lots, price, **kw): return await self._run(self.sync.sell_limit, symbol, lots, price, **kw)
    async def buy_stop(self, symbol, lots, price, **kw): return await self._run(self.sync.buy_stop, symbol, lots, price, **kw)
    async def sell_stop(self, symbol, lots, price, **kw): return await self._run(self.sync.sell_stop, symbol, lots, price, **kw)
    async def modify_sl_tp(self, symbol, position_ticket, sl=0.0, tp=0.0): return await self._run(self.sync.modify_sl_tp, symbol, position_ticket, sl, tp)
    async def modify_pending(self, symbol, order_ticket, price, sl=0.0, tp=0.0): return await self._run(self.sync.modify_pending, symbol, order_ticket, price, sl, tp)
    async def cancel_order(self, symbol, order_ticket): return await self._run(self.sync.cancel_order, symbol, order_ticket)
    async def close_position(self, symbol, ticket, lots=None, pos_type='BUY'): return await self._run(self.sync.close_position, symbol, ticket, lots, pos_type)

    # -- positions
    async def get_positions(self): return await self._run(self.sync.get_positions)
    async def get_pending_orders(self): return await self._run(self.sync.get_pending_orders)
    async def get_positions_and_orders(self): return await self._run(self.sync.get_positions_and_orders)
    async def close_all(self, symbol=None): return await self._run(self.sync.close_all, symbol)

    # -- events and threads (non-blocking)
    def on_tick(self, callback): self.sync.on_tick(callback)
    def on_trade(self, callback): self.sync.on_trade(callback)
    def on_position_change(self, callback): self.sync.on_position_change(callback)
    def start_tick_listener(self): return self.sync.start_tick_listener()
    def stop_tick_listener(self): self.sync.stop_tick_listener()
    def start_heartbeat(self, interval=30): return self.sync.start_heartbeat(interval)
    def stop_heartbeat(self): self.sync.stop_heartbeat()
    def close(self): self.sync.close()

    # -- state
    @property
    def host(self): return self.sync.host
    @property
    def address(self): return self.sync.address
    @property
    def endpoint(self): return self.sync.endpoint
    @property
    def symbol_list(self): return self.sync.symbol_list
    @property
    def symbol_map(self): return self.sync.symbol_map
