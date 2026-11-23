import struct
from typing import Optional

from ..constants.commands import CMD_ACCOUNT, CMD_HISTORY, CMD_INIT_TRADING
from ..models import AccountInfo, AccountSummary, Deal, Frame, HistoryOrder
from ..parsers import parse_account, parse_history, parse_positions, summarize_account
from .base import BaseService


class AccountService(BaseService):
    def get_account_info(self) -> Optional[AccountInfo]:
        """Static account record. Also remembers the leverage for position margin."""
        info = parse_account(self.request(CMD_ACCOUNT, timeout=10))
        if info and info.leverage:
            self.state.leverage = info.leverage
        return info

    def get_account_summary(self) -> Optional[AccountSummary]:
        """Account record plus equity, margin and floating profit from the open positions."""
        info = self.get_account_info()
        if info is None:
            return None
        resp = self.init_trading()
        positions = parse_positions(resp.payload, self.state.leverage) if resp else []
        return summarize_account(info, positions)

    def init_trading(self) -> Optional[Frame]:
        """Raw init-trading reply; its payload carries the open positions and pending orders."""
        return self.request(CMD_INIT_TRADING, timeout=10)

    def get_history(self, from_ts: int = 0, to_ts: int = 0) -> tuple[list[Deal], list[HistoryOrder]]:
        resp = self.request(CMD_HISTORY, struct.pack('<II', from_ts, to_ts), timeout=30)
        if not resp:
            return [], []
        return parse_history(resp.payload)
