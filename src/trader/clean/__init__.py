"""Clean: verifies and stores market history, adjusting for corporate actions. Writes data/history/.

It asks one question of every figure: did this happen in the market? Never why.
When it cannot verify a share, the share sits out the day with a reason ("don't know").
Design: docs/design/pass4-fetch-clean.md.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import Counter

from trader.schema import ACTION_FIELDS, INDEX_FIELDS, PRICE_FIELDS, RESTART
from trader.store import Store, month_file

from . import parse

MAX_UNEXPLAINED_MOVE = 0.25   # larger moves with no corporate action sit out one day
MAX_ADJUSTED_MOVE = 0.21      # a split is verified if the price, scaled by its ratio, moved no more than a day can
                              # (20% is NSE's widest daily price band; CGCL rose exactly 20% on its split day in 2024)
NOTICE_DAYS = 10              # in a backfill, an announcement is treated as known this many days before it takes effect


class Cleaner:
    def __init__(self, store: Store):
        self.w = store.writer("clean")
        history = store.history()
        self.last = {s: (b.date, b.close) for s, b in history.latest_bars().items()}
        self.prev_day = max((d for d, _ in self.last.values()), default=None)
        self.actions = {(a.symbol, a.ex_date, a.kind): _Known(a.factor, a.status, a.known_from)
                        for a in history.all_actions()}
        self.isin = {}
        identity = store.history_dir / "identity.csv"
        if identity.exists():
            with open(identity, newline="") as f:
                for r in csv.DictReader(f):
                    self.isin[r["symbol"]] = r["isin"]
        self.pending = {}
        for key, a in self.actions.items():
            if a.status == "announced":
                self.pending.setdefault(key[0], []).append(key)

    def add_announcements(self, body: bytes, seen: dt.date, backfill: bool) -> int:
        """Records corporate actions not seen before. Returns how many were new."""
        new = []
        for a in parse.corporate_actions(body):
            ex = dt.date.fromisoformat(a["ex_date"])
            key = (a["symbol"], ex, a["kind"])
            if key in self.actions:
                continue
            known = ex - dt.timedelta(days=NOTICE_DAYS) if backfill else seen
            line = {**a, "seen": seen.isoformat(), "status": "announced", "known_from": known.isoformat()}
            new.append(line)
            self.actions[key] = _Known(a["factor"], "announced", known)
            self.pending.setdefault(a["symbol"], []).append(key)
        self._write_actions(seen, new)
        return len(new)

    def clean_day(self, d: dt.date, price_file: bytes, index_file: bytes | None) -> dict:
        rows = parse.price_rows(price_file)
        counts = Counter(r["symbol"] for r in rows)
        stored, skipped, action_lines, identity = [], [], [], []
        for r in rows:
            s = r["symbol"]
            reason = None
            try:
                o, h, l, c, p = (float(r[k]) for k in ("open", "high", "low", "close", "prev_close"))
                float(r["volume"]), float(r["value"]), int(float(r["trades"] or 0))
            except ValueError:
                o = h = l = c = p = 0.0
                reason = "a figure is not a number"
            if reason is None and counts[s] > 1:
                reason = "appears more than once in the file"
            elif reason is None and not (0 < l <= min(o, c) and max(o, c) <= h and p > 0):
                reason = "prices are not consistent (low, open, close, high)"
            last_date, last_close = self.last.get(s, (None, None))
            effective = self._takes_effect(s, last_date, d)
            if reason is None and last_date is not None and last_date == self.prev_day and abs(p - last_close) > 0.011:
                reason = f"previous close {p} does not match stored close {last_close}"
            if reason is None and effective:
                # Actions taking effect together (e.g. a split and a bonus on one day) are checked together.
                factor = 1.0
                for key in effective:
                    if key[2] != RESTART:
                        factor *= self.actions[key].factor
                restarts = any(key[2] == RESTART for key in effective)  # the series restarts anyway: no price check
                ok = last_close is None or restarts or abs(c * factor / last_close - 1) <= MAX_ADJUSTED_MOVE
                if not ok:
                    reason = f"corporate action of {factor:g}x does not match the price move; history restarts"
                for key in effective:
                    a = self.actions[key]
                    status = "verified" if ok or key[2] == RESTART else "rejected"
                    self.actions[key] = _Known(a.factor, status, a.known_from)
                    self.pending[s].remove(key)
                    action_lines.append({"symbol": s, "ex_date": key[1].isoformat(), "kind": key[2], "factor": a.factor,
                                         "status": status, "seen": d.isoformat(), "known_from": a.known_from.isoformat(),
                                         "subject": f"checked against the price on {d.isoformat()}"})
                if not ok:
                    # Unverifiable: drop the share's earlier history rather than keep an unexplained jump in it.
                    self.actions[(s, d, RESTART)] = _Known(1.0, "verified", d)
                    action_lines.append({"symbol": s, "ex_date": d.isoformat(), "kind": RESTART, "factor": 1.0,
                                         "status": "verified", "seen": d.isoformat(), "known_from": d.isoformat(),
                                         "subject": "history restarts: corporate action could not be verified"})
                    self.last.pop(s, None)
            elif reason is None and last_date == self.prev_day and abs(c / p - 1) > MAX_UNEXPLAINED_MOVE:
                reason = f"moved {c / p - 1:+.0%} with no corporate action; sitting out one day"
            if reason:
                skipped.append({"date": d.isoformat(), "symbol": s, "reason": reason})
                continue
            stored.append({k: r[k] for k in PRICE_FIELDS})
            self.last[s] = (d, c)
            if self.isin.get(s) != r["isin"]:
                identity.append({"symbol": s, "isin": r["isin"], "from": d.isoformat()})
                self.isin[s] = r["isin"]
        present = set(counts)
        for s, (last_date, _) in sorted(self.last.items()):
            if last_date == self.prev_day and s not in present:
                skipped.append({"date": d.isoformat(), "symbol": s, "reason": "not traded today"})
        self.w.append_csv(f"prices/{month_file(d, 'csv')}", PRICE_FIELDS, stored)
        if skipped:
            self.w.append_records(f"skipped/{month_file(d, 'jsonl')}", skipped)
        self._write_actions(d, action_lines)
        if identity:
            self.w.append_csv("identity.csv", ["symbol", "isin", "from"], identity)
        if index_file:
            self.w.append_csv(f"index/{month_file(d, 'csv')}", INDEX_FIELDS, parse.index_rows(index_file))
        self.prev_day = d
        return {"stored": len(stored), "skipped": len(skipped), "actions_checked": len(action_lines)}

    def _takes_effect(self, symbol: str, last_date: dt.date | None, d: dt.date) -> list:
        """Announced actions whose effective date falls after the share's last stored day, up to today."""
        return [k for k in self.pending.get(symbol, []) if k[1] <= d and (last_date is None or k[1] > last_date)]

    def _write_actions(self, d: dt.date, lines: list[dict]) -> None:
        if lines:
            self.w.append_csv(f"actions/{month_file(d, 'csv')}", ACTION_FIELDS, lines)


class _Known:
    def __init__(self, factor: float, status: str, known_from: dt.date):
        self.factor, self.status, self.known_from = factor, status, known_from
