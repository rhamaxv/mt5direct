import struct
from typing import Optional, Union

from ..constants.commands import CMD_RESOLVE, CMD_SUBSCRIBE, CMD_SYMBOL_TYPES, CMD_SYMBOLS
from ..models import Frame, Symbol
from ..parsers import (
    extract_resolve_prices, find_resolve_bid_offset, parse_symbols, parse_trade_modes,
    parse_trade_sessions,
)
from .base import BaseService


def _ta_payload(ta_list: list[int]) -> bytes:
    return struct.pack(f'<{1 + len(ta_list)}I', len(ta_list), *ta_list)


class SymbolService(BaseService):
    def get_symbol_types(self) -> Optional[Frame]:
        return self.request(CMD_SYMBOL_TYPES, timeout=10)

    def get_symbols(self) -> list[Symbol]:
        """Download the symbol table and refresh the name/ta lookup maps."""
        resp = self.request(CMD_SYMBOLS, timeout=30)
        if resp is None or resp.status != 0:
            return []
        self.state.set_symbols(parse_symbols(resp.payload))
        return self.state.symbols

    def resolve_symbols(self, ta_list: list[int]) -> Optional[Frame]:
        return self.request(CMD_RESOLVE, _ta_payload(ta_list), timeout=15)

    def subscribe(self, ta_values: Union[int, list[int]]) -> None:
        if isinstance(ta_values, int):
            ta_values = [ta_values]
        self.session.send(CMD_SUBSCRIBE, _ta_payload(ta_values))

    def subscribe_by_name(self, *names: str) -> None:
        ta_list = [self.state.symbol_map[n].ta for n in names if n in self.state.symbol_map]
        if ta_list:
            self.resolve_symbols(ta_list)
            self.subscribe(ta_list)

    def subscribe_all(self) -> tuple[int, bytes]:
        """Resolve and subscribe every known symbol. Returns ``(count, resolve_payload)``."""
        all_ta = [s.ta for s in self.state.symbols]
        resolve_data = b''
        if all_ta:
            resp = self.resolve_symbols(all_ta)
            if resp:
                resolve_data = resp.payload
            self.subscribe(all_ta)
        return len(all_ta), resolve_data

    def parse_trade_sessions(self, resolve_data: bytes):
        return parse_trade_sessions(resolve_data, self.state.symbols)

    def parse_trade_modes(self, resolve_data: bytes):
        return parse_trade_modes(resolve_data, self.state.symbols)

    def find_resolve_bid_offset(self, resolve_data: bytes, sym_name: str, expected_price: float,
                                digits: int, tolerance: float = 0.02):
        return find_resolve_bid_offset(resolve_data, self.state.symbols, sym_name,
                                       expected_price, digits, tolerance)

    def extract_resolve_prices(self, resolve_data: bytes, bid_offset: int):
        return extract_resolve_prices(resolve_data, self.state.symbols, bid_offset)
