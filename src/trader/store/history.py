"""Reads the stored market history, as of a date.

Every job reads prices through HistoryView, which cannot see anything after
its date. Splits and bonuses are applied to earlier prices only once their
effective date has passed (pass4-fetch-clean.md, "without looking at the future").
"""

from __future__ import annotations

import bisect
import csv
import datetime as dt
from collections import defaultdict
from pathlib import Path

from trader.schema import RESTART, Action, Bar, to_date


class History:
    def __init__(self, bars: dict[str, list[Bar]], actions: list[Action], index: dict[str, list[tuple[dt.date, float]]]):
        self._bars = {s: sorted(b, key=lambda x: x.date) for s, b in bars.items()}
        self._dates = {s: [x.date for x in b] for s, b in self._bars.items()}
        self._actions = defaultdict(list)
        for a in actions:
            self._actions[a.symbol].append(a)
        self._index = {k: sorted(v) for k, v in index.items()}
        self.calendar = sorted({d for ds in self._dates.values() for d in ds})

    @classmethod
    def load(cls, history_dir: Path) -> History:
        bars = defaultdict(list)
        for path in sorted((history_dir / "prices").glob("*.csv")):
            with open(path, newline="") as f:
                for r in csv.DictReader(f):
                    bars[r["symbol"]].append(Bar(
                        to_date(r["date"]), r["symbol"], float(r["open"]), float(r["high"]), float(r["low"]),
                        float(r["close"]), float(r["prev_close"]), float(r["volume"]), float(r["value"]), int(r["trades"]),
                    ))
        latest = {}
        for path in sorted((history_dir / "actions").glob("*.csv")):
            with open(path, newline="") as f:
                for r in csv.DictReader(f):
                    key = (r["symbol"], r["ex_date"], r["kind"])
                    latest[key] = Action(r["symbol"], to_date(r["ex_date"]), r["kind"], float(r["factor"]),
                                         r["status"], to_date(r["known_from"]), r["subject"])
        for path in sorted((history_dir / "renames").glob("*.csv")):
            with open(path, newline="") as f:
                for r in csv.DictReader(f):  # a renamed share keeps its history under its new symbol
                    old = [b for b in bars.pop(r["old"], [])]
                    bars[r["new"]] = [Bar(b.date, r["new"], b.open, b.high, b.low, b.close, b.prev_close, b.volume,
                                          b.value, b.trades) for b in old] + bars[r["new"]]
        index = defaultdict(list)
        for path in sorted((history_dir / "index").glob("*.csv")):
            with open(path, newline="") as f:
                for r in csv.DictReader(f):
                    index[r["index"]].append((to_date(r["date"]), float(r["close"])))
        return cls(bars, list(latest.values()), index)

    def latest_bars(self) -> dict[str, Bar]:
        """Each symbol's most recent stored bar, unadjusted."""
        return {s: b[-1] for s, b in self._bars.items() if b}

    def all_actions(self) -> list[Action]:
        return [a for acts in self._actions.values() for a in acts]

    def as_of(self, date: dt.date) -> HistoryView:
        return HistoryView(self, date)


class HistoryView:
    """Market history exactly as it was known at the close of `date`."""

    def __init__(self, history: History, date: dt.date):
        self._h = history
        self.date = date
        self.calendar = history.calendar[: bisect.bisect_right(history.calendar, date)]

    def symbols(self) -> list[str]:
        return [s for s, ds in self._h._dates.items() if ds and ds[0] <= self.date]

    def raw_bar(self, symbol: str, date: dt.date | None = None) -> Bar | None:
        """The unadjusted bar for one day (default: today), or None."""
        date = date or self.date
        if date > self.date:
            raise LookupError(f"{date} is after {self.date}")
        ds = self._h._dates.get(symbol, [])
        i = bisect.bisect_left(ds, date)
        return self._h._bars[symbol][i] if i < len(ds) and ds[i] == date else None

    def bars(self, symbol: str) -> list[Bar]:
        """Every bar up to today, adjusted for splits and bonuses that have taken effect by today."""
        ds = self._h._dates.get(symbol, [])
        bars = self._h._bars.get(symbol, [])[: bisect.bisect_right(ds, self.date)]
        effective = [a for a in self._h._actions.get(symbol, []) if a.status == "verified" and a.ex_date <= self.date]
        for a in effective:
            if a.kind == RESTART:
                bars = [b for b in bars if b.date >= a.ex_date]
        scaling = [a for a in effective if a.kind != RESTART]
        if not scaling:
            return bars
        out = []
        for b in bars:
            f = 1.0
            for a in scaling:
                if b.date < a.ex_date:
                    f *= a.factor
            if f == 1.0:
                out.append(b)
            else:
                out.append(Bar(b.date, b.symbol, b.open / f, b.high / f, b.low / f, b.close / f,
                               b.prev_close / f, b.volume * f, b.value, b.trades))
        return out

    def actions_known(self) -> list[Action]:
        """Every action announced by today, including ones that take effect later."""
        return [a for acts in self._h._actions.values() for a in acts if a.known_from <= self.date]

    def verified_action(self, symbol: str, ex_date: dt.date) -> Action | None:
        if ex_date > self.date:
            raise LookupError(f"{ex_date} is after {self.date}")
        for a in self._h._actions.get(symbol, []):
            if a.ex_date == ex_date and a.status == "verified" and a.kind != RESTART:
                return a
        return None

    def index_closes(self, name: str) -> list[float]:
        rows = self._h._index.get(name, [])
        return [c for d, c in rows[: bisect.bisect_right(rows, (self.date, float("inf")))]]
