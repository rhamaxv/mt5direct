import asyncio
import inspect

from mt5direct import AsyncMT5Client, MT5Client


def test_async_wraps_sync_client_methods():
    a = AsyncMT5Client(host="fake.example:1951")
    assert isinstance(a.sync, MT5Client)
    assert a.address == "fake.example:1951"
    for name in ("connect", "login", "buy", "get_positions", "get_pending_orders", "get_symbol_info",
                 "get_account_summary", "get_candles_df"):
        assert inspect.iscoroutinefunction(getattr(a, name)), name
    for name in ("on_tick", "on_trade", "on_position_change", "start_heartbeat", "close"):
        assert not inspect.iscoroutinefunction(getattr(a, name)), name


def test_async_call_runs_in_thread():
    a = AsyncMT5Client(host="fake.example")
    a.sync.on_tick(lambda t: None)
    result = asyncio.run(a._run(lambda x: x * 2, 21))
    assert result == 42
