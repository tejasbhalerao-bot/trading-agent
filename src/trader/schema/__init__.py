"""The shapes jobs hand each other. Jobs share nothing else."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass

PRICE_FIELDS = ["date", "symbol", "open", "high", "low", "close", "prev_close", "volume", "value", "trades"]
ACTION_FIELDS = ["seen", "symbol", "ex_date", "kind", "factor", "status", "known_from", "subject"]
INDEX_FIELDS = ["date", "index", "open", "high", "low", "close"]

# Corporate action kinds Clean acts on. "restart" = demerger or scheme: the price series restarts.
SPLIT, BONUS, RESTART = "split", "bonus", "restart"


@dataclass(frozen=True)
class Bar:
    date: dt.date
    symbol: str
    open: float
    high: float
    low: float
    close: float
    prev_close: float
    volume: float
    value: float
    trades: int

    @property
    def locked(self) -> bool:
        """Stuck at a price limit: almost nobody could trade."""
        return self.high == self.low


@dataclass(frozen=True)
class Action:
    symbol: str
    ex_date: dt.date
    kind: str
    factor: float  # new shares per old share: a 1-for-5 split is 5, a 1:1 bonus is 2
    status: str  # announced | verified | rejected
    known_from: dt.date
    subject: str


def entry_id(date: dt.date, symbol: str, checklist: str) -> str:
    """The fixed ID shared by a candidate, its proposal, decision and result."""
    return f"{date.isoformat()}/{symbol}/{checklist}"


def to_date(s: str) -> dt.date:
    return dt.date.fromisoformat(s)
