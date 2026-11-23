"""Readers for the per-symbol metadata block returned by the resolve command.

The 3068-byte record layout is only partially known; the probe helpers below
were used to locate fields and are kept for further reverse engineering.
"""

import struct
from typing import Sequence

from ..models import Symbol
from ..protocol import BinaryReader
from ..protocol.layouts import (
    RESOLVE_DAY_BLOCK_SIZE, RESOLVE_RECORD_SIZE, RESOLVE_SESSION_OFFSET,
    RESOLVE_TRADE_MODE_OFFSET,
)


def parse_trade_sessions(resolve_data: bytes, symbols: Sequence[Symbol]) -> dict[int, list[tuple[int, int]]]:
    """Map ``ta`` to seven ``(start, end)`` minute pairs, Sunday first."""
    data = resolve_data[4:]
    r = BinaryReader(data)
    sessions = {}
    for i, sym in enumerate(symbols):
        rec_off = i * RESOLVE_RECORD_SIZE
        if rec_off + RESOLVE_RECORD_SIZE > len(data):
            break
        days = []
        for d in range(7):
            off = rec_off + RESOLVE_SESSION_OFFSET + d * RESOLVE_DAY_BLOCK_SIZE
            if off + 4 <= len(data):
                days.append((r.u16(off), r.u16(off + 2)))
            else:
                days.append((0, 0))
        sessions[sym.ta] = days
    return sessions


def parse_trade_modes(resolve_data: bytes, symbols: Sequence[Symbol]) -> dict[int, int]:
    data = resolve_data[4:]
    r = BinaryReader(data)
    modes = {}
    for i, sym in enumerate(symbols):
        rec_off = i * RESOLVE_RECORD_SIZE + RESOLVE_TRADE_MODE_OFFSET
        if rec_off + 4 <= len(data):
            modes[sym.ta] = r.u32(rec_off)
    return modes


def find_resolve_bid_offset(resolve_data: bytes, symbols: Sequence[Symbol], sym_name: str,
                            expected_price: float, digits: int, tolerance: float = 0.02):
    """Scan one symbol's record for values near ``expected_price`` in several encodings.

    Returns ``(record_index, [(offset, value, encoding), ...])`` or ``(-1, [])``.
    """
    data = resolve_data[4:]
    idx = None
    for i, sym in enumerate(symbols):
        if sym.name == sym_name:
            idx = i
            break
    if idx is None:
        return -1, []
    rec = data[idx * RESOLVE_RECORD_SIZE:(idx + 1) * RESOLVE_RECORD_SIZE]
    matches = []
    for off in range(0, len(rec) - 8, 4):
        val = struct.unpack('<d', rec[off:off + 8])[0]
        if expected_price > 0 and abs(val - expected_price) / expected_price < tolerance:
            matches.append((off, val, 'f64'))
    scaled = int(expected_price * (10 ** digits))
    for off in range(0, len(rec) - 4, 4):
        val = struct.unpack('<I', rec[off:off + 4])[0]
        if abs(val - scaled) <= scaled * tolerance:
            matches.append((off, val / (10 ** digits), 'u32_scaled'))
    for off in range(0, len(rec) - 8, 4):
        val = struct.unpack('<q', rec[off:off + 8])[0]
        if val > 0 and abs(val - scaled) <= scaled * tolerance:
            matches.append((off, val / (10 ** digits), 'i64_scaled'))
    return idx, matches


def extract_resolve_prices(resolve_data: bytes, symbols: Sequence[Symbol], bid_offset: int) -> dict[str, float]:
    data = resolve_data[4:]
    r = BinaryReader(data)
    prices = {}
    for i, sym in enumerate(symbols):
        rec_off = i * RESOLVE_RECORD_SIZE + bid_offset
        if rec_off + 8 <= len(data):
            prices[sym.name] = r.f64(rec_off)
    return prices
