"""Runs the real jobs over history. Writes data/backtest/ only.

1. Replays every evening over the period into a work folder outside the repo, exactly as
   the live system would have run (Claude's review left out: it would know the future).
2. Gathers every candidate that was settled: the trades taken, and the shadow trades for
   candidates skipped. Each checklist is judged on all of its candidates, not only the
   few that fitted the account.
3. Measures each checklist, and each checklist in each market mood, under three cost
   assumptions, by year as well as overall.
4. Writes the starting trust scores (per-cell totals) that Learn reads, and every trade,
   so each starting score points back to the trades behind it.

Design: docs/design/pass1-decide-record-learn.md (M5), docs/reports/m5.md.
"""

from __future__ import annotations

import datetime as dt
import math
import statistics
from collections import defaultdict
from pathlib import Path

from trader.evening import replay
from trader.store import Store, month_file

# Round-trip costs as a share of the trade value, in percent.
COSTS = {
    "none": 0.0,                 # your current setting (costs ignored for now)
    "taxes_and_fees": 0.25,      # transaction tax 0.1% each side, stamp duty, exchange fees; a broker charging no brokerage
    "with_flat_fees": 1.25,      # plus about ₹20 of flat charges per round trip on a ₹2,000 position (your account's size)
}
Z90 = 1.645


def run_backtest(repo: Store, work_root: Path, start: dt.date, end: dt.date, run_id: str) -> dict:
    work = Store(work_root, history_from=repo.history_dir.parent.parent)
    replay(work, start, end, quiet=True)
    trades = collect(work)
    cost_now = repo.config("costs")["round_trip_cost_pct"]
    w = repo.writer("backtest")
    by_month = defaultdict(list)
    for t in trades:
        by_month[t["date"][:7]].append({"type": "trade", "run": run_id, **t})
    for month, rows in sorted(by_month.items()):
        w.append_records(f"trades/{month}.jsonl", rows)
    stats = summarize(trades)
    portfolio = account_path(work)
    today = dt.date.today()
    summary = [{"type": "run", "run": run_id, "date": today.isoformat(), "code_version": repo.code_version(),
                "period": [start.isoformat(), end.isoformat()], "trades": len(trades), "costs_pct": COSTS,
                "prior_cost_pct": cost_now, "portfolio": portfolio}]
    summary += [{"type": "stats", "run": run_id, **s} for s in stats]
    summary += [{"type": "cell_summary", "run": run_id, **c} for c in priors(trades, cost_now)]
    w.append_records(month_file(today, "jsonl"), summary)
    return {"trades": len(trades), "stats": stats, "portfolio": portfolio}


def collect(work: Store) -> list[dict]:
    """Every settled candidate, taken or shadow, with what is needed to judge it."""
    mood = {}
    for r in work.records_all("notebook"):
        if r["type"] in ("decision", "skip") and r.get("checklist"):
            mood[r["id"]] = r.get("mood", "unknown")
    out = []
    for e in work.records_all("books"):
        if e["type"] != "event":
            continue
        kind = e["event"].replace("shadow_", "")
        if kind not in ("exited", "unknown") or "entry" not in e:
            continue
        t = {"id": e["id"], "date": e["date"], "symbol": e["symbol"], "checklist": e.get("checklist"),
             "mood": mood.get(e["id"], "unknown"), "taken": not e["event"].startswith("shadow_"),
             "outcome": kind, "reason": e.get("reason"), "entry": e["entry"], "stop": e["stop"]}
        if kind == "exited":
            t["exit"] = e["price"]
        else:
            t["exit_worse"], t["exit_better"] = e["worse"], e["better"]
        out.append(t)
    return out


def _returns(t: dict, cost_pct: float) -> tuple[float, float, float]:
    """(net % at the cautious end, net % at the generous end, net R at the cautious end)."""
    lo = t.get("exit", t.get("exit_worse"))
    hi = t.get("exit", t.get("exit_better"))
    risk_pct = (t["entry"] - t["stop"]) / t["entry"] * 100
    p_lo = (lo / t["entry"] - 1) * 100 - cost_pct
    p_hi = (hi / t["entry"] - 1) * 100 - cost_pct
    return p_lo, p_hi, (p_lo / risk_pct if risk_pct > 0 else 0.0)


def _group(trades: list[dict], cost_pct: float) -> dict:
    n = len(trades)
    rows = [_returns(t, cost_pct) for t in trades]
    lo = [r[0] for r in rows]
    mean = statistics.mean(lo)
    sd = statistics.stdev(lo) if n > 1 else 0.0
    years = defaultdict(list)
    for t, r in zip(trades, rows):
        years[t["date"][:4]].append(r[0])
    by_year = {y: round(statistics.mean(v), 3) for y, v in sorted(years.items())}
    return {
        "trades": n, "unknown": sum(t["outcome"] == "unknown" for t in trades),
        "win_rate": [round(sum(x > 0 for x in lo) / n, 3), round(sum(r[1] > 0 for r in rows) / n, 3)],
        "avg_return_pct": [round(mean, 3), round(statistics.mean(r[1] for r in rows), 3)],
        "avg_return_pct_low90": round(mean - Z90 * sd / math.sqrt(n), 3) if n > 1 else None,
        "avg_r": round(statistics.mean(r[2] for r in rows), 3),
        "by_year": by_year, "years_positive": sum(v > 0 for v in by_year.values()), "years": len(by_year),
    }


def summarize(trades: list[dict]) -> list[dict]:
    groups = {("all", "*"): trades}
    for t in trades:
        groups.setdefault(("checklist", t["checklist"]), []).append(t)
        groups.setdefault(("cell", f"{t['checklist']}|{t['mood']}"), []).append(t)
    out = []
    for (level, key), ts in sorted(groups.items()):
        for name, cost in COSTS.items():
            if ts:
                out.append({"level": level, "key": key, "costs": name, **_group(ts, cost)})
    return out


def priors(trades: list[dict], cost_pct: float) -> list[dict]:
    """Starting trust scores, in the form Learn reads: totals per cell, per checklist and overall."""
    cells = defaultdict(list)
    for t in trades:
        cells[(t["checklist"], t["mood"])].append(t)
        cells[(t["checklist"], "*")].append(t)
        cells["*"].append(t)
    out = []
    for key, ts in cells.items():
        rows = [_returns(t, cost_pct) for t in ts]
        out.append({"cell": list(key) if isinstance(key, tuple) else key, "n": len(ts),
                    "wins": sum(r[0] > 0 for r in rows), "sum_r": round(sum(r[2] for r in rows), 3)})
    return out


def account_path(work: Store) -> dict:
    """How the practice account itself would have fared: the spec asks how it behaves through losing runs."""
    snaps = [r for r in work.records_all("books") if r["type"] == "snapshot"]
    if not snaps:
        return {}
    worst, peak = 0.0, snaps[0]["balance_worse"]
    for s in snaps:
        peak = max(peak, s["balance_worse"])
        worst = max(worst, 1 - s["balance_worse"] / peak)
    brake = defaultdict(int)
    for r in work.records_all("notebook"):
        if r["type"] == "run" and r["stage"] == "proposed":
            brake[r.get("brake", "normal")] += 1
    taken = sum(1 for e in work.records_all("books") if e["type"] == "event" and e["event"] == "entered")
    return {"start": snaps[0]["balance_worse"], "end": snaps[-1]["balance_worse"], "worst_fall_pct": round(worst * 100, 1),
            "trades_taken": taken, "days_by_brake": dict(brake), "days": len(snaps)}
