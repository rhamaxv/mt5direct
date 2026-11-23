from typing import Optional

from ..constants.orders import TRADE_MODE_NAMES
from ..models import Symbol, SymbolInfo
from ..protocol import BinaryReader, raw_to_vol
from ..protocol.layouts import (
    RESOLVE_CONTRACT_SIZE_OFFSET, RESOLVE_RECORD_SIZE, RESOLVE_TRADE_MODE_OFFSET,
    RESOLVE_VOLUME_MAX_OFFSET, RESOLVE_VOLUME_MIN_OFFSET, RESOLVE_VOLUME_STEP_OFFSET,
)


def parse_symbol_info(record: bytes, symbol: Symbol) -> Optional[SymbolInfo]:
    """Decode one 3068-byte resolve record into a trading specification."""
    if len(record) < RESOLVE_RECORD_SIZE:
        return None
    r = BinaryReader(record)
    digits = symbol.digits
    trade_mode = r.u32(RESOLVE_TRADE_MODE_OFFSET)
    contract_size = r.f64(RESOLVE_CONTRACT_SIZE_OFFSET)
    tick_size = 10 ** (-digits) if digits >= 0 else 0
    return SymbolInfo(
        name=symbol.name,
        digits=digits,
        description=symbol.description,
        path=symbol.path,
        trade_mode=TRADE_MODE_NAMES.get(trade_mode, f'MODE_{trade_mode}'),
        trade_mode_id=trade_mode,
        contract_size=contract_size,
        tick_size=tick_size,
        tick_value=contract_size * tick_size,
        volume_min=raw_to_vol(r.u64(RESOLVE_VOLUME_MIN_OFFSET)),
        volume_max=raw_to_vol(r.u64(RESOLVE_VOLUME_MAX_OFFSET)),
        volume_step=raw_to_vol(r.u64(RESOLVE_VOLUME_STEP_OFFSET)),
    )


def parse_symbol_infos(resolve_payload: bytes, symbols: list[Symbol]) -> dict[str, SymbolInfo]:
    """Records in the resolve reply appear in the order the symbols were requested."""
    data = resolve_payload[4:]
    out = {}
    for idx, sym in enumerate(symbols):
        info = parse_symbol_info(data[idx * RESOLVE_RECORD_SIZE:(idx + 1) * RESOLVE_RECORD_SIZE], sym)
        if info is None:
            break
        out[sym.name] = info
    return out
