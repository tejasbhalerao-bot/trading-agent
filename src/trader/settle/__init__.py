"""Settle: works out fills and the account from real prices. Writes data/books/.

Gross only, never asks you, never guesses: a day that touched both the stop and the
target is unknown and valued both ways. Design: docs/design/pass2-settle.md.
"""

from __future__ import annotations

import math

from trader.store import Store
from trader.store.history import HistoryView

MAX_WAIT_DAYS = 5


def settle_day(store: Store, view: HistoryView, starting_balance: float) -> dict:
    d = view.date
    w = store.writer("settle")
    path = f"{d.year}.jsonl"
    state = _last_snapshot(store, d) or {"cash_worse": starting_balance, "cash_better": starting_balance,
                                         "positions": [], "pending": [], "peak": starting_balance}
    cash_w, cash_b = state["cash_worse"], state["cash_better"]
    positions, pending = state["positions"], state["pending"]
    events = []

    def event(p, kind, **kw):
        events.append({"type": "event", "date": d.isoformat(), "id": p["id"], "symbol": p["symbol"], "event": kind, **kw})

    # New buys decided on the previous trading day join the queue.
    prev_day = view.calendar[-2] if len(view.calendar) > 1 else None
    for r in _decisions(store, prev_day):
        pending.append({"id": r["id"], "symbol": r["symbol"], "qty": r["quantity"], "stop": r["stop"],
                        "target": r["target"], "max_hold": r["max_hold_days"], "waited": 0})

    # Entries
    still_pending = []
    for p in pending:
        bar = view.raw_bar(p["symbol"])
        action = view.verified_action(p["symbol"], d) if bar else None
        if action:
            p = _scale(p, action.factor)
            event(p, "adjusted", factor=action.factor, reason=f"{action.kind} took effect")
        if bar is None:
            p["waited"] += 1
            if p["waited"] >= MAX_WAIT_DAYS:
                event(p, "not_entered", reason="no price")
            else:
                event(p, "waiting", reason="no price yet")
                still_pending.append(p)
            continue
        if bar.locked:
            event(p, "not_entered", reason="could not trade")
            continue
        if bar.open <= p["stop"] or bar.open >= p["target"]:
            event(p, "not_entered", reason="opened beyond its exit", price=bar.open)
            continue
        qty = min(p["qty"], math.floor(cash_w / bar.open))
        if qty <= 0:
            event(p, "not_entered", reason="not enough cash", price=bar.open)
            continue
        if qty < p["qty"]:
            event(p, "quantity_cut", reason="not enough cash", qty=qty)
        cash_w -= qty * bar.open
        cash_b -= qty * bar.open
        positions.append({"id": p["id"], "symbol": p["symbol"], "qty": qty, "entry": bar.open, "stop": p["stop"],
                          "stop_at_entry": p["stop"], "target": p["target"], "max_hold": p["max_hold"],
                          "days": 0, "waited": 0, "entered": d.isoformat(), "last_close": bar.open})
        event(positions[-1], "entered", price=bar.open, qty=qty)
    pending = still_pending

    # Exits, checked in the order the design gives
    still_open = []
    for p in positions:
        bar = view.raw_bar(p["symbol"])
        if bar is None:
            p["waited"] += 1
            if p["waited"] >= MAX_WAIT_DAYS:
                cash_w += p["qty"] * p["stop"]
                cash_b += p["qty"] * p["target"]
                event(p, "unknown", reason="no price for 5 trading days", worse=p["stop"], better=p["target"])
            else:
                still_open.append(p)
            continue
        p["waited"] = 0
        action = view.verified_action(p["symbol"], d)
        if action and p["entered"] != d.isoformat():
            p = _scale(p, action.factor)
            event(p, "adjusted", factor=action.factor, reason=f"{action.kind} took effect")
        first_day = p["entered"] == d.isoformat()
        exit_price, reason = None, None
        if bar.locked:
            pass
        elif p["days"] >= p["max_hold"]:
            exit_price, reason = bar.open, "time limit"
        elif not first_day and bar.open <= p["stop"]:
            exit_price, reason = bar.open, "gapped through the stop"
        elif not first_day and bar.open >= p["target"]:
            exit_price, reason = bar.open, "gapped through the target"
        elif bar.low <= p["stop"] and bar.high >= p["target"]:
            cash_w += p["qty"] * p["stop"]
            cash_b += p["qty"] * p["target"]
            event(p, "unknown", reason="the day touched both the stop and the target", worse=p["stop"], better=p["target"])
            continue
        elif bar.low <= p["stop"]:
            exit_price, reason = p["stop"], "stop"
        elif bar.high >= p["target"]:
            exit_price, reason = p["target"], "target"
        if exit_price is not None:
            cash_w += p["qty"] * exit_price
            cash_b += p["qty"] * exit_price
            event(p, "exited", price=exit_price, reason=reason)
            continue
        if not bar.locked:
            p["days"] += 1
        p["last_close"] = bar.close
        still_open.append(p)
    positions = still_open

    held = sum(p["qty"] * p["last_close"] for p in positions)
    snapshot = {"type": "snapshot", "date": d.isoformat(), "cash_worse": round(cash_w, 2), "cash_better": round(cash_b, 2),
                "balance_worse": round(cash_w + held, 2), "balance_better": round(cash_b + held, 2),
                "positions": positions, "pending": pending}
    snapshot["gap"] = round(snapshot["balance_better"] - snapshot["balance_worse"], 2)
    snapshot["peak"] = max(state["peak"], snapshot["balance_worse"])
    w.append_records(path, events + [snapshot])
    return {"events": len(events), "open": len(positions), "balance_worse": snapshot["balance_worse"]}


def _scale(p: dict, factor: float) -> dict:
    """A split or bonus: more shares at proportionally lower prices. Value and risk unchanged."""
    p = dict(p)
    p["qty"] = int(round(p["qty"] * factor))
    for k in ("entry", "stop", "stop_at_entry", "target", "last_close"):
        if k in p:
            p[k] = p[k] / factor
    return p


def _last_snapshot(store: Store, d) -> dict | None:
    for year in (d.year, d.year - 1):
        for r in reversed(store.records(f"books/{year}.jsonl")):
            if r["type"] == "snapshot" and r["date"] < d.isoformat():
                return r
    return None


def _decisions(store: Store, day) -> list[dict]:
    if day is None:
        return []
    return [r for r in store.records(f"notebook/{day.year}.jsonl")
            if r["type"] == "decision" and r["action"] == "buy" and r["date"] == day.isoformat()]
