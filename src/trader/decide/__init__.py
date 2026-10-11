"""Decide: picks buys and exits from candidates, within the safety limits.

Writes nothing itself; Record writes its proposals. Same inputs, same output.
Design: docs/design/pass1-decide-record-learn.md.

M3 slice: no trust scores yet, so candidates are ranked by traded value, and there is no
confidence and no losing-run brake. Both arrive in M4.
"""

from __future__ import annotations

import math

from trader.schema import entry_id
from trader.store import Store
from trader.store.history import HistoryView


def decide(store: Store, view: HistoryView) -> tuple[list[dict], list[dict]]:
    """Returns (proposals, skips) for tomorrow."""
    d = view.date
    limits = store.config("limits")
    checklists = store.checklists()
    books = _snapshot(store, d) or {}
    balance = books.get("balance_worse", limits["paper_starting_balance_inr"])
    cash = books.get("cash_worse", balance)
    positions = books.get("positions", [])
    pending = books.get("pending", [])
    held = {p["symbol"] for p in positions + pending}
    open_risk = sum(p["qty"] * max(p.get("entry", p["stop"]) - p["stop"], 0) for p in positions)

    proposals = []
    for p in positions:
        if p["days"] >= p["max_hold"]:
            proposals.append({"id": p["id"], "date": d.isoformat(), "action": "exit", "symbol": p["symbol"],
                              "quantity": p["qty"], "reason": "time limit: sell at tomorrow's open"})

    checks = [r for r in store.records(f"analysis/{d.year}.jsonl") if r["type"] == "check" and r["date"] == d.isoformat()]
    mood = next((r["mood"] for r in store.records(f"analysis/{d.year}.jsonl")
                 if r["type"] == "mood" and r["date"] == d.isoformat()), "unknown")
    candidates = [(r, cid) for r in checks for cid, res in r["results"].items() if res["pass"]]
    candidates.sort(key=lambda rc: (-rc[0]["figures"]["value"], rc[0]["symbol"], rc[1]))

    skips, chosen = [], set()
    slots = limits["max_open_positions"] - len(positions) - len(pending)
    for r, cid in candidates:
        s, f, exits = r["symbol"], r["figures"], checklists[cid]["exits"]
        cand = entry_id(d, s, cid)

        def skip(reason, **extra):
            skips.append({"id": cand, "date": d.isoformat(), "symbol": s, "checklist": cid, "reason": reason, **extra})

        if s in held:
            skip("already held")
            continue
        if s in chosen:
            skip("already proposed under another checklist")
            continue
        if slots <= 0:
            skip(f"no room: {limits['max_open_positions']} positions open or proposed")
            continue
        close, move = f["close"], f["typical_daily_move"]
        stop = round(close - exits["stop_typical_moves"] * move, 2)
        target = round(close + exits["target_typical_moves"] * move, 2)
        per_share = close - stop
        sizes = {
            "risk per trade": math.floor(balance * limits["risk_per_trade_pct"] / 100 / per_share),
            "max position size": math.floor(balance * limits["max_position_size_pct"] / 100 / close),
            "max total open risk": math.floor((balance * limits["max_total_open_risk_pct"] / 100 - open_risk) / per_share),
            "cash on hand": math.floor(cash / close),
        }
        qty = min(sizes.values())
        if qty <= 0:
            skip("cannot afford one share within the limits", limited_by=min(sizes, key=sizes.get), close=close)
            continue
        limited_by = min(sizes, key=sizes.get)
        open_risk += qty * per_share
        cash -= qty * close
        slots -= 1
        chosen.add(s)
        proposals.append({
            "id": cand, "date": d.isoformat(), "action": "buy", "symbol": s, "checklist": cid, "mood": mood,
            "quantity": qty, "entry_estimate": close, "stop": stop, "target": target,
            "max_hold_days": exits["max_hold_days"], "risk_amount": round(qty * per_share, 2), "size_limited_by": limited_by,
            "candidate": f"{d.isoformat()}/{s}", "figures": f, "trust_version": None, "confidence": None,
            "reasons": (f"{checklists[cid]['name']}: every condition met. Buy {qty} at tomorrow's open (about ₹{close:,.2f}); "
                        f"stop ₹{stop:,.2f}, target ₹{target:,.2f}, sell after {exits['max_hold_days']} trading days. "
                        f"Size set by {limited_by}."),
        })
    return proposals, skips


def _snapshot(store: Store, d) -> dict | None:
    for year in (d.year, d.year - 1):
        for r in reversed(store.records(f"books/{year}.jsonl")):
            if r["type"] == "snapshot" and r["date"] <= d.isoformat():
                return r
    return None
