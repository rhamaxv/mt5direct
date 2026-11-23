from typing import Optional

from ..constants.commands import CMD_ACCOUNT, CMD_HISTORY, CMD_INIT_TRADING
from ..models import AccountInfo, Deal, Frame, HistoryOrder
from ..parsers import parse_account, parse_history
from .base import BaseService
import struct


class AccountService(BaseService):
    def get_account_info(self) -> Optional[AccountInfo]:
        return parse_account(self.request(CMD_ACCOUNT, timeout=10))

    def init_trading(self) -> Optional[Frame]:
        """Raw init-trading reply; its payload carries the open-position list."""
        return self.request(CMD_INIT_TRADING, timeout=10)

    def get_history(self, from_ts: int = 0, to_ts: int = 0) -> tuple[list[Deal], list[HistoryOrder]]:
        resp = self.request(CMD_HISTORY, struct.pack('<II', from_ts, to_ts), timeout=30)
        if not resp:
            return [], []
        return parse_history(resp.payload)
