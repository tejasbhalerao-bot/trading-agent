"""Decide: picks buys and exits from candidates, within the safety limits.

Writes nothing itself; Record writes its proposals. Same inputs, same output.
Learning decides what to buy (ranking, confidence, switched-off cells); only the
safety limits decide how much. Design: docs/design/pass1-decide-record-learn.md.
"""

from __future__ import annotations

import math

from trader.schema import entry_id
from trader.store import Store, month_file
from trader.store.history import HistoryView


def decide(store: Store, view: HistoryView, trust: dict | None) -> tuple[list[dict], list[dict], dict]:
    """Returns (proposals, skips, brake) for tomorrow. `trust` is the latest trust version, or None."""
    d = view.date
    limits = store.config("limits")
    checklists = store.checklists()
    snapshots = [r for r in store.records_all("books") if r["type"] == "snapshot" and r["date"] <= d.isoformat()]
    books = snapshots[-1] if snapshots else {}
    balance = books.get("balance_worse", limits["paper_starting_balance_inr"])
    cash = books.get("cash_worse", balance)
    positions, pending = books.get("positions", []), books.get("pending", [])
    held = {p["symbol"] for p in positions + pending}
    open_risk = sum(p["qty"] * max(p["entry"] - p["stop"], 0) for p in positions)
    brake = brake_state(snapshots, limits)
    risk_pct = limits["risk_per_trade_pct"] * (0.5 if brake["mode"] in ("half", "half after pause") else 1)

    proposals = []
    for p in positions:
        if p["days"] >= p["max_hold"]:
            proposals.append({"id": p["id"], "date": d.isoformat(), "action": "exit", "symbol": p["symbol"],
                              "quantity": p["qty"], "reason": "time limit: sell at tomorrow's open"})

    today = store.records(f"analysis/{month_file(d, 'jsonl')}")
    checks = [r for r in today if r["type"] == "check" and r["date"] == d.isoformat()]
    mood = next((r["mood"] for r in today if r["type"] == "mood" and r["date"] == d.isoformat()), "unknown")
    cells = (trust or {}).get("cells", {})
    candidates = []
    for r in checks:
        for cid, res in r["results"].items():
            if res["pass"]:
                cell = cells.get(f"{cid}|{mood}", {})
                exits = checklists[cid]["exits"]
                close, move = r["figures"]["close"], r["figures"]["typical_daily_move"]
                candidates.append({
                    "r": r, "cid": cid, "cell": cell, "close": close,
                    "stop": round(close - exits["stop_typical_moves"] * move, 2),
                    "target": round(close + exits["target_typical_moves"] * move, 2),
                    "max_hold": exits["max_hold_days"],
                    "expected_r": cell.get("expected_r", 0.0), "confidence": cell.get("confidence"),
                })
    candidates.sort(key=lambda c: (-c["expected_r"], -c["r"]["figures"]["value"], c["r"]["symbol"], c["cid"]))

    skips, chosen = [], set()
    slots = limits["max_open_positions"] - len(positions) - len(pending)
    for c in candidates:
        s, cid = c["r"]["symbol"], c["cid"]
        base = {"id": entry_id(d, s, cid), "date": d.isoformat(), "symbol": s, "checklist": cid, "mood": mood,
                "stop": c["stop"], "target": c["target"], "max_hold_days": c["max_hold"],
                "expected_r": c["expected_r"], "confidence": c["confidence"]}

        def skip(reason, **extra):
            skips.append({**base, "reason": reason, **extra})

        if c["cell"].get("switched_off"):
            skip(f"{checklists[cid]['name']} is switched off in a {mood} market: even its best case loses")
            continue
        if brake["mode"] == "paused":
            skip(f"losing-run brake: no new buys for {brake['until']}")
            continue
        if s in held:
            skip("already held")
            continue
        if s in chosen:
            skip("already proposed under another checklist")
            continue
        if slots <= 0:
            skip(f"no room: {limits['max_open_positions']} positions open or proposed")
            continue
        per_share = c["close"] - c["stop"]
        sizes = {
            "risk per trade": math.floor(balance * risk_pct / 100 / per_share),
            "max position size": math.floor(balance * limits["max_position_size_pct"] / 100 / c["close"]),
            "max total open risk": math.floor((balance * limits["max_total_open_risk_pct"] / 100 - open_risk) / per_share),
            "cash on hand": math.floor(cash / c["close"]),
        }
        qty, limited_by = min(sizes.values()), min(sizes, key=sizes.get)
        if qty <= 0:
            skip("cannot afford one share within the limits", limited_by=limited_by, close=c["close"])
            continue
        open_risk += qty * per_share
        cash -= qty * c["close"]
        slots -= 1
        chosen.add(s)
        name = checklists[cid]["name"]
        conf = f"{c['confidence']:.0%}" if c["confidence"] is not None else "not yet measured"
        proposals.append({
            **base, "action": "buy", "quantity": qty, "entry_estimate": c["close"],
            "risk_amount": round(qty * per_share, 2), "size_limited_by": limited_by, "brake": brake["mode"],
            "candidate": f"{d.isoformat()}/{s}", "figures": c["r"]["figures"],
            "trust_version": (trust or {}).get("version"),
            "reasons": (f"{name}: every condition met in a {mood} market. Buy {qty} at tomorrow's open "
                        f"(about ₹{c['close']:,.2f}); stop ₹{c['stop']:,.2f}, target ₹{c['target']:,.2f}, "
                        f"sell after {c['max_hold']} trading days. Confidence {conf}. Size set by {limited_by}."),
        })
    return proposals, skips, brake


def brake_state(snapshots: list[dict], limits: dict) -> dict:
    """The losing-run brake, worked out from the account's history. Automatic: nothing waits for you.

    normal -> half (10% below the highest balance) -> paused for 10 trading days (15% below)
    -> half after pause (no new pause) -> normal once back within 10%.
    """
    b = limits["losing_run_brake"]
    mode, until_i = "normal", None
    for i, s in enumerate(snapshots):
        fall = (1 - s["balance_worse"] / s["peak"]) * 100 if s["peak"] else 0.0
        if mode == "paused" and i >= until_i:
            mode = "half after pause"
        if mode == "paused":
            continue
        if fall < b["halve_risk_below_peak_pct"]:
            mode = "normal"
        elif mode == "normal":
            mode = "half"
        if mode == "half" and fall >= b["pause_new_buys_below_peak_pct"]:
            mode, until_i = "paused", i + b["pause_trading_days"]
    fall = (1 - snapshots[-1]["balance_worse"] / snapshots[-1]["peak"]) * 100 if snapshots else 0.0
    until = f"{until_i - len(snapshots) + 1} more trading day(s)" if mode == "paused" else None
    return {"mode": mode, "fall_below_peak_pct": round(fall, 2), "until": until}
