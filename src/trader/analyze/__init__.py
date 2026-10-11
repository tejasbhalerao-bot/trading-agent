"""Analyze: market mood, and every share against every checklist. Writes data/analysis/.

Reports facts only: no ranking, no scoring. Design: docs/design/pass3-analyze.md.
"""

from __future__ import annotations

import datetime as dt
import statistics

from trader.schema import RESTART, SPLIT, BONUS
from trader.store import Store, month_file
from trader.store.history import HistoryView

from .conditions import CONDITIONS, typical_daily_move

UNIVERSE_SIZE = 500
UNIVERSE_WINDOW = 60
MIN_HISTORY = 61          # 60 days of history before today
ACTION_WINDOW_DAYS = 7    # calendar days ahead: covers the 4 trading days a trade can be open
MOOD_INDEX = "Nifty 500"


def analyze_day(store: Store, view: HistoryView) -> dict:
    d = view.date
    w = store.writer("analyze")
    path = month_file(d, "jsonl")
    universe = _universe(store, view, w, path)
    mood = _mood(view)
    w.append_records(path, [{"type": "mood", "date": d.isoformat(), **mood}])

    checklists = store.checklists()
    soon = {a.symbol for a in view.actions_known()
            if a.kind in (SPLIT, BONUS, RESTART) and d < a.ex_date <= d + dt.timedelta(days=ACTION_WINDOW_DAYS)}
    lines, matches = [], 0
    for s in sorted(universe):
        bars = view.bars(s)
        figures, shared_fail = {}, None
        if not bars or bars[-1].date != d:
            shared_fail = "not_traded_today"
        elif len(bars) < MIN_HISTORY:
            shared_fail = "not_enough_history"
        elif bars[-1].locked:
            shared_fail = "locked_at_price_limit"
        elif s in soon:
            shared_fail = "corporate_action_within_holding_period"
        else:
            b = bars[-1]
            figures = {"open": b.open, "high": b.high, "low": b.low, "close": b.close, "prev_close": b.prev_close,
                       "volume": b.volume, "value": b.value, "typical_daily_move": round(typical_daily_move(bars), 4)}
        results = {}
        for cid, checklist in checklists.items():
            if shared_fail:
                results[cid] = {"pass": False, "failed": shared_fail}
                continue
            failed = None
            for cond in checklist["conditions"]:
                (name, params), = cond.items()
                ok, figs = CONDITIONS[name](bars, **params)
                figures.update(figs)
                if not ok and failed is None:
                    failed = name
            results[cid] = {"pass": failed is None, "failed": failed}
            matches += failed is None
        lines.append({"type": "check", "date": d.isoformat(), "symbol": s, "figures": figures, "results": results})
    w.append_records(path, lines)
    return {"universe": len(universe), "checked": len(lines), "matches": matches, "mood": mood["mood"]}


def _universe(store: Store, view: HistoryView, w, path: str) -> list[str]:
    """The month's 500 shares with the highest median traded value over the previous 60 trading days."""
    d = view.date
    month = f"{d.year}-{d.month:02d}"
    for r in reversed(store.records(f"analysis/{path}")):
        if r["type"] == "universe":
            if r["month"] == month:
                return r["symbols"]
            break
    window = view.calendar[-UNIVERSE_WINDOW - 1:-1]
    ranked = []
    for s in view.symbols():
        values = [b.value if (b := view.raw_bar(s, day)) else 0.0 for day in window]
        ranked.append((statistics.median(values), s))
    ranked.sort(key=lambda x: (-x[0], x[1]))
    top = ranked[:UNIVERSE_SIZE]
    w.append_records(path, [{"type": "universe", "date": d.isoformat(), "month": month,
                             "symbols": [s for _, s in top], "median_values": [round(v) for v, _ in top]}])
    return [s for _, s in top]


def _mood(view: HistoryView) -> dict:
    closes = view.index_closes(MOOD_INDEX)
    if len(closes) < 60:
        return {"mood": "unknown", "reason": f"only {len(closes)} days of {MOOD_INDEX}"}
    dma, dma_then = sum(closes[-50:]) / 50, sum(closes[-60:-10]) / 50
    if closes[-1] > dma and dma > dma_then:
        mood = "up"
    elif closes[-1] < dma and dma < dma_then:
        mood = "down"
    else:
        mood = "sideways"
    return {"mood": mood, "index_close": closes[-1], "dma50": round(dma, 2), "dma50_10_days_ago": round(dma_then, 2)}
