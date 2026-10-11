"""Learn: updates trust scores from the finished notebook. Writes data/trust/.

Design: docs/design/pass1-decide-record-learn.md ("Confidence", "Trust scores", "Learn").
- Only taken trades move trust scores; skipped candidates only become suggestions.
- Unknowns are never dropped: every figure is a range (unknowns as losses / as wins).
- Judged net of the cost estimate (currently zero).
- Every version lists the notebook entries behind it.
"""

from __future__ import annotations

import datetime as dt
import math
import statistics

from trader.store import Store, month_file

BACKTEST_WEIGHT = 0.25   # a backtest trade counts a quarter of a paper trade...
BACKTEST_CAP = 20        # ...and the backtest can never outweigh 20 paper trades
POOL = 5                 # how strongly thin evidence borrows from the level above
MIN_TRADES_TO_SWITCH_OFF = 10
MIN_TRADES_FOR_CALIBRATION = 10
MIN_TRADES_TO_CHANGE_WEIGHT = 30
Z90 = 1.645


def learn_day(store: Store, d: dt.date) -> dict | None:
    """Writes a new trust version if any result arrived since the last one. Returns it, or None."""
    decisions = {r["id"]: r for r in store.records_all("notebook") if r["type"] == "decision" and r["action"] == "buy"}
    results = [r for r in store.records_all("notebook")
               if r["type"] == "result" and r["outcome"] != "not_entered" and r["date"] <= d.isoformat()]
    shadows = [r for r in store.records_all("books")
               if r["type"] == "event" and r["event"] in ("shadow_exited", "shadow_unknown") and r["date"] <= d.isoformat()]
    last = latest_version(store, d)
    if last and last["evidence_count"] == len(results) and last["shadow_count"] == len(shadows):
        return None
    cost_pct = store.config("costs")["round_trip_cost_pct"]
    trades = [t for t in (_trade(r, decisions.get(r["id"]), cost_pct) for r in results) if t]
    prior = _backtest_prior(store)

    weight = last["backtest_weight"] if last else BACKTEST_WEIGHT
    weight_changed_at = last["weight_changed_at"] if last else 0
    calibration, overall = _calibration(trades)
    changes = []
    if (overall and overall["verdict"] == "overconfident" and len(trades) >= MIN_TRADES_TO_CHANGE_WEIGHT
            and len(trades) - weight_changed_at >= MIN_TRADES_TO_CHANGE_WEIGHT):
        weight /= 2
        weight_changed_at = len(trades)
        changes.append(f"Confidence ran too high over {len(trades)} trades: backtest weight halved to {weight:g}.")

    g = _estimate(trades, prior.get("*"), weight, 0.5, 0.0)
    checklists, cells = {}, {}
    for cid in sorted({t["checklist"] for t in trades} | {k[0] for k in prior if k != "*" and isinstance(k, tuple)} | set(store.checklists())):
        ct = [t for t in trades if t["checklist"] == cid]
        checklists[cid] = _estimate(ct, prior.get((cid, "*")), weight, g["confidence"], g["expected_r"])
        for mood in ("up", "down", "sideways"):
            mt = [t for t in ct if t["mood"] == mood]
            est = _estimate(mt, prior.get((cid, mood)), weight, checklists[cid]["confidence"], checklists[cid]["expected_r"])
            est["switched_off"] = _losing(mt)
            est["evidence"] = [t["id"] for t in mt]
            cells[f"{cid}|{mood}"] = est

    if last:
        for key, est in cells.items():
            before = last["cells"].get(key)
            new = [i for i in est["evidence"] if not before or i not in set(before["evidence"])]
            if not before or new or before["switched_off"] != est["switched_off"]:
                changes.append({"cell": key, "new_results": new,
                                "confidence": [before and before["confidence"], est["confidence"]],
                                "expected_r": [before and before["expected_r"], est["expected_r"]],
                                "switched_off": est["switched_off"]})

    version = {
        "type": "trust", "version": (last["version"] + 1) if last else 1, "date": d.isoformat(),
        "code_version": store.code_version(), "evidence_count": len(results), "shadow_count": len(shadows),
        "backtest_weight": weight, "weight_changed_at": weight_changed_at, "backtest_run": prior.get("run"),
        "cost_pct": cost_pct, "overall": g, "checklists": checklists, "cells": cells,
        "calibration": calibration, "calibration_overall": overall, "changes": changes,
        "suggestions": _suggestions(trades, shadows),
    }
    store.writer("learn").append_records(month_file(d, "jsonl"), [version])
    return version


def latest_version(store: Store, d: dt.date) -> dict | None:
    for r in reversed(store.records_all("trust")):
        if r["type"] == "trust" and r["date"] <= d.isoformat():
            return r
    return None


def _trade(result: dict, decision: dict | None, cost_pct: float) -> dict | None:
    if not decision:
        return None
    entry = result.get("entry_price")
    if entry is None:
        return None
    risk_pct = (entry - decision["stop"]) / entry * 100
    cost_r = cost_pct / risk_pct if risk_pct > 0 else 0.0
    if result["outcome"] == "exited":
        lo = hi = (result["r_multiple"] or 0.0) - cost_r
    else:
        lo, hi = (result["r_multiple_worse"] or -1.0) - cost_r, (result["r_multiple_better"] or 1.0) - cost_r
    return {"id": result["id"], "checklist": decision["checklist"], "mood": decision.get("mood", "unknown"),
            "confidence": decision.get("confidence"), "r_floor": lo, "r_ceiling": hi,
            "win_floor": lo > 0, "win_ceiling": hi > 0, "unknown": result["outcome"] == "unknown"}


def _estimate(trades: list[dict], prior: dict | None, weight: float, parent_p: float, parent_r: float) -> dict:
    """Smoothed win rate and expected R (cautious end), plus the raw ranges, for one group of trades."""
    n = len(trades)
    wins_lo = sum(t["win_floor"] for t in trades)
    wins_hi = sum(t["win_ceiling"] for t in trades)
    r_lo = [t["r_floor"] for t in trades]
    r_hi = [t["r_ceiling"] for t in trades]
    bn, bw, br = (prior["n"], prior["wins"], prior["sum_r"]) if prior else (0, 0, 0.0)
    w = min(weight, BACKTEST_CAP / bn) if bn else 0.0
    denom = n + w * bn + POOL
    return {
        "paper_trades": n, "unknown": sum(t["unknown"] for t in trades), "backtest_trades": bn,
        "win_rate_range": [_rate(wins_lo, n), _rate(wins_hi, n)],
        "avg_r_range": [_mean(r_lo), _mean(r_hi)],
        "confidence": round((wins_lo + w * bw + POOL * parent_p) / denom, 4),
        "expected_r": round((sum(r_lo) + w * br + POOL * parent_r) / denom, 4),
    }


def _losing(trades: list[dict]) -> bool:
    """Switched off during paper trading once even the most generous estimate is below zero."""
    if len(trades) < MIN_TRADES_TO_SWITCH_OFF:
        return False
    r = [t["r_ceiling"] for t in trades]
    upper = statistics.mean(r) + Z90 * statistics.stdev(r) / math.sqrt(len(r))
    return upper < 0


def _calibration(trades: list[dict]) -> tuple[list[dict], dict | None]:
    rated = [t for t in trades if t["confidence"] is not None]
    bins = []
    for lo in [i / 10 for i in range(10)]:
        group = [t for t in rated if lo <= t["confidence"] < lo + 0.1 or (lo == 0.9 and t["confidence"] == 1.0)]
        if group:
            bins.append({"from": lo, "to": round(lo + 0.1, 1), **_verdict(group)})
    return bins, (_verdict(rated) if rated else None)


def _verdict(group: list[dict]) -> dict:
    n = len(group)
    stated = sum(t["confidence"] for t in group) / n
    lo, hi = sum(t["win_floor"] for t in group), sum(t["win_ceiling"] for t in group)
    low_bound, high_bound = _wilson(lo, n)[0], _wilson(hi, n)[1]
    if n < MIN_TRADES_FOR_CALIBRATION:
        verdict = "not enough trades yet"
    elif stated > high_bound:
        verdict = "overconfident"
    elif stated < low_bound:
        verdict = "underconfident"
    else:
        verdict = "honest"
    return {"trades": n, "stated": round(stated, 3), "happened": [_rate(lo, n), _rate(hi, n)],
            "margin": [round(low_bound, 3), round(high_bound, 3)], "verdict": verdict}


def _suggestions(trades: list[dict], shadows: list[dict]) -> list[str]:
    """Skipped candidates never move trust scores; they can only prompt a human to look."""
    out = []
    for cid in sorted({s["checklist"] for s in shadows if s.get("checklist")}):
        sh = [s for s in shadows if s.get("checklist") == cid]
        if len(sh) < 10:
            continue
        lo = sum(1 for s in sh if s["event"] == "shadow_exited" and s["r_multiple"] > 0)
        hi = lo + sum(1 for s in sh if s["event"] == "shadow_unknown")
        taken = [t for t in trades if t["checklist"] == cid]
        t_hi = sum(t["win_ceiling"] for t in taken)
        if taken and lo / len(sh) > t_hi / len(taken):
            out.append(f"{cid}: skipped candidates won {lo}–{hi} of {len(sh)}, more often than taken trades "
                       f"({t_hi} of {len(taken)} at best). Worth a human look at how candidates are ranked.")
    return out


def _backtest_prior(store: Store) -> dict:
    """Per-cell totals from the latest backtest run (M5). Empty until then."""
    rows = [r for r in store.records_all("backtest") if r["type"] == "cell_summary"]
    if not rows:
        return {}
    run = rows[-1]["run"]
    prior = {"run": run}
    for r in rows:
        if r["run"] == run:
            prior[tuple(r["cell"]) if r["cell"] != "*" else "*"] = r
    return prior


def _wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return 0.0, 1.0
    p, z = k / n, Z90
    centre = (p + z * z / (2 * n)) / (1 + z * z / n)
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
    return max(0.0, centre - half), min(1.0, centre + half)


def _rate(k: int, n: int) -> float | None:
    return round(k / n, 3) if n else None


def _mean(xs: list[float]) -> float | None:
    return round(statistics.mean(xs), 3) if xs else None
