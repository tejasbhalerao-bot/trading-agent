"""Settle: works out fills and the account from real prices. Writes data/books/.

Gross only, never asks you, never guesses: a day that touched both the stop and the
target is unknown and valued both ways. Design: docs/design/pass2-settle.md.

Skipped candidates are also settled, as "shadow" trades outside the account, so Learn
can raise suggestions about them. They never touch the balance or the trust scores.
"""

from __future__ import annotations

import math

from trader.store import Store, month_file
from trader.store.history import HistoryView

MAX_WAIT_DAYS = 5


def settle_day(store: Store, view: HistoryView, starting_balance: float) -> dict:
    d = view.date
    state = _last_snapshot(store, d) or {"cash_worse": starting_balance, "cash_better": starting_balance,
                                         "positions": [], "pending": [], "shadows": [], "peak": starting_balance}
    cash = {"worse": state["cash_worse"], "better": state["cash_better"]}
    events = []

    def event(p, kind, **kw):
        events.append({"type": "event", "date": d.isoformat(), "id": p["id"], "symbol": p["symbol"], "event": kind,
                       **({"checklist": p["checklist"]} if p.get("checklist") else {}), **kw})

    prev_day = view.calendar[-2] if len(view.calendar) > 1 else None
    pending = state["pending"] + [_order(r) for r in _decided(store, prev_day, "decision")]
    shadow_orders = [_order(r) for r in _decided(store, prev_day, "skip") if r.get("stop") is not None]

    # Entries
    positions, still_pending = list(state["positions"]), []
    for p in pending:
        outcome = _enter(p, view, event)
        if outcome == "wait":
            still_pending.append(p)
        elif outcome:
            qty = min(p["qty"], math.floor(cash["worse"] / outcome))
            if qty <= 0:
                event(p, "not_entered", reason="not enough cash", price=outcome)
                continue
            if qty < p["qty"]:
                event(p, "quantity_cut", reason="not enough cash", qty=qty)
            for k in cash:
                cash[k] -= qty * outcome
            positions.append(_position(p, qty, outcome, d))
            event(positions[-1], "entered", price=outcome, qty=qty)
    shadows = list(state.get("shadows", []))
    for p in shadow_orders:
        outcome = _enter(p, view, lambda q, kind, **kw: event(q, f"shadow_{kind}", **kw), wait=False)
        if outcome:
            shadows.append(_position(p, 1, outcome, d))

    # Exits
    still_open = []
    for p in positions:
        done = _exit(p, view, event)
        if done is None:
            still_open.append(p)
        else:
            cash["worse"] += p["qty"] * done[0]
            cash["better"] += p["qty"] * done[1]
    still_shadow = []
    for p in shadows:
        done = _exit(p, view, lambda q, kind, **kw: event(q, f"shadow_{kind}", **kw))
        if done is None:
            still_shadow.append(p)

    held = sum(p["qty"] * p["last_close"] for p in still_open)
    snapshot = {"type": "snapshot", "date": d.isoformat(), "cash_worse": round(cash["worse"], 2),
                "cash_better": round(cash["better"], 2), "balance_worse": round(cash["worse"] + held, 2),
                "balance_better": round(cash["better"] + held, 2), "positions": still_open, "pending": still_pending,
                "shadows": still_shadow}
    snapshot["gap"] = round(snapshot["balance_better"] - snapshot["balance_worse"], 2)
    snapshot["peak"] = max(state["peak"], snapshot["balance_worse"])
    store.writer("settle").append_records(month_file(d, "jsonl"), events + [snapshot])
    return {"events": len(events), "open": len(still_open), "balance_worse": snapshot["balance_worse"]}


def _order(r: dict) -> dict:
    return {"id": r["id"], "symbol": r["symbol"], "checklist": r.get("checklist"), "qty": r.get("quantity", 1),
            "stop": r["stop"], "target": r["target"], "max_hold": r["max_hold_days"], "waited": 0}


def _position(p: dict, qty: int, price: float, d) -> dict:
    return {"id": p["id"], "symbol": p["symbol"], "checklist": p.get("checklist"), "qty": qty, "entry": price,
            "stop": p["stop"], "target": p["target"], "max_hold": p["max_hold"], "days": 0, "waited": 0,
            "entered": d.isoformat(), "last_close": price}


def _enter(p: dict, view: HistoryView, event, wait: bool = True):
    """Entry table: returns the entry price, "wait", or None (not entered)."""
    bar = view.raw_bar(p["symbol"])
    if bar is None:
        p["waited"] += 1
        if wait and p["waited"] < MAX_WAIT_DAYS:
            event(p, "waiting", reason="no price yet")
            return "wait"
        event(p, "not_entered", reason="no price for 5 trading days")
        return None
    action = view.verified_action(p["symbol"], view.date)
    if action:
        p.update(_scaled(p, action.factor))
        event(p, "adjusted", factor=action.factor, reason=f"{action.kind} took effect")
    if bar.locked:
        event(p, "not_entered", reason="could not trade")
        return None
    if bar.open <= p["stop"] or bar.open >= p["target"]:
        event(p, "not_entered", reason="opened beyond its exit", price=bar.open)
        return None
    return bar.open


def _exit(p: dict, view: HistoryView, event):
    """Exit table, in the design's order. Returns None if still held, else (worse, better) exit prices."""
    d = view.date
    bar = view.raw_bar(p["symbol"])
    if bar is None:
        p["waited"] += 1
        if p["waited"] >= MAX_WAIT_DAYS:
            event(p, "unknown", reason="no price for 5 trading days", worse=p["stop"], better=p["target"],
                  **_r_both(p))
            return p["stop"], p["target"]
        return None
    p["waited"] = 0
    action = view.verified_action(p["symbol"], d)
    if action and p["entered"] != d.isoformat():
        p.update(_scaled(p, action.factor))
        event(p, "adjusted", factor=action.factor, reason=f"{action.kind} took effect")
    first_day = p["entered"] == d.isoformat()
    price, reason = None, None
    if bar.locked:
        pass
    elif p["days"] >= p["max_hold"]:
        price, reason = bar.open, "time limit"
    elif not first_day and bar.open <= p["stop"]:
        price, reason = bar.open, "gapped through the stop"
    elif not first_day and bar.open >= p["target"]:
        price, reason = bar.open, "gapped through the target"
    elif bar.low <= p["stop"] and bar.high >= p["target"]:
        event(p, "unknown", reason="the day touched both the stop and the target", worse=p["stop"], better=p["target"],
              **_r_both(p))
        return p["stop"], p["target"]
    elif bar.low <= p["stop"]:
        price, reason = p["stop"], "stop"
    elif bar.high >= p["target"]:
        price, reason = p["target"], "target"
    if price is not None:
        event(p, "exited", price=price, reason=reason, entry=p["entry"], **_r(p, price))
        return price, price
    if not bar.locked:
        p["days"] += 1
    p["last_close"] = bar.close
    return None


def _r(p: dict, price: float) -> dict:
    risk = p["entry"] - p["stop"]
    return {"r_multiple": round((price - p["entry"]) / risk, 3)} if risk > 0 else {}


def _r_both(p: dict) -> dict:
    risk = p["entry"] - p["stop"]
    if risk <= 0:
        return {}
    return {"r_multiple_worse": round((p["stop"] - p["entry"]) / risk, 3),
            "r_multiple_better": round((p["target"] - p["entry"]) / risk, 3)}


def _scaled(p: dict, factor: float) -> dict:
    """A split or bonus: more shares at proportionally lower prices. Value and risk unchanged."""
    out = {"qty": int(round(p["qty"] * factor))}
    for k in ("entry", "stop", "target", "last_close"):
        if k in p:
            out[k] = p[k] / factor
    return out


def _last_snapshot(store: Store, d) -> dict | None:
    for r in reversed(store.records_all("books")):
        if r["type"] == "snapshot" and r["date"] < d.isoformat():
            return r
    return None


def _decided(store: Store, day, kind: str) -> list[dict]:
    if day is None:
        return []
    return [r for r in store.records(f"notebook/{month_file(day, 'jsonl')}")
            if r["type"] == kind and r.get("action", "buy") == "buy" and r["date"] == day.isoformat()]
