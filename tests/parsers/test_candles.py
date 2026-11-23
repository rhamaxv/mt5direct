import struct

from mt5direct.parsers import parse_candles


def _candle(ts, o, h, lo, c, vol, spread):
    return struct.pack('<idddd', ts, o, h, lo, c) + struct.pack('<qi', vol, spread)


def test_parse_candles_ignores_partial_trailing_record():
    payload = _candle(1, 1.0, 2.0, 0.5, 1.5, 10, 3) + _candle(2, 1.5, 2.5, 1.0, 2.0, 20, 4) + b'\x00' * 5
    candles = parse_candles(payload)
    assert len(candles) == 2
    assert candles[0].time == 1 and candles[0].open == 1.0 and candles[0].high == 2.0
    assert candles[0].low == 0.5 and candles[0].close == 1.5
    assert candles[0].tick_volume == 10 and candles[0].spread == 3
    assert candles[1].time == 2


def test_parse_candles_empty():
    assert parse_candles(b'') == []
