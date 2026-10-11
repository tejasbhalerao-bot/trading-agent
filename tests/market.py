"""A small synthetic market for tests: deterministic prices written as Clean would store them."""

from __future__ import annotations

import csv
import datetime as dt
import random
from pathlib import Path

from trader.schema import ACTION_FIELDS, INDEX_FIELDS, PRICE_FIELDS, Bar
from trader.store.history import History

START = dt.date(2025, 1, 1)


def trading_days(n: int, start: dt.date = START) -> list[dt.date]:
    days, d = [], start
    while len(days) < n:
        if d.weekday() < 5:
            days.append(d)
        d += dt.timedelta(days=1)
    return days


def make_market(root: Path, n_symbols: int = 30, n_days: int = 140, seed: int = 7,
                change_after: dt.date | None = None) -> list[dt.date]:
    """Writes data/history under root. With change_after, every price after that date is
    different, while everything up to it is identical to the unchanged market."""
    rng, later = random.Random(seed), random.Random(seed + 1000)
    days = trading_days(n_days)
    hist = root / "data" / "history"
    for sub in ("prices", "index", "actions"):
        (hist / sub).mkdir(parents=True, exist_ok=True)
    rows, index_rows, level = [], [], 1000.0
    closes = {f"S{i:02d}": 100.0 + 10 * i for i in range(n_symbols)}
    for d in days:
        r = later if change_after and d > change_after else rng
        level *= 1 + r.gauss(0.0005, 0.008)
        index_rows.append({"date": d, "index": "Nifty 500", "open": level, "high": level, "low": level, "close": level})
        for s in closes:
            prev = closes[s]
            o = prev * (1 + r.gauss(0, 0.004))
            c = o * (1 + r.gauss(0.0005, 0.01))
            h, l = max(o, c) * (1 + abs(r.gauss(0, 0.004))), min(o, c) * (1 - abs(r.gauss(0, 0.004)))
            v = 100_000 * (3 if r.random() < 0.08 else 1) * (1 + r.random())
            rows.append({"date": d, "symbol": s, "open": round(o, 2), "high": round(h, 2), "low": round(l, 2),
                         "close": round(c, 2), "prev_close": round(prev, 2), "volume": round(v), "value": round(v * c),
                         "trades": 1000})
            closes[s] = round(c, 2)
    _write(hist / "prices" / "2025.csv", PRICE_FIELDS, rows)
    _write(hist / "index" / "2025.csv", INDEX_FIELDS, index_rows)
    _write(hist / "actions" / "2025.csv", ACTION_FIELDS, [])
    return days


def history_of(bars: dict[str, list[tuple]], actions=(), start: dt.date = START) -> History:
    """A History from (open, high, low, close) tuples per symbol, one per trading day."""
    days = trading_days(max(len(v) for v in bars.values()), start)
    out = {}
    for s, ohlc in bars.items():
        out[s] = [Bar(d, s, o, h, l, c, c, 1000, 1000 * c, 10) for d, (o, h, l, c) in zip(days, ohlc)]
    return History(out, list(actions), {})


def _write(path: Path, fields: list[str], rows: list[dict]) -> None:
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, lineterminator="\n")
        w.writeheader()
        w.writerows(rows)
