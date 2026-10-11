"""Watchers: the daily report. Read-only: nothing in the system reads what it produces.

render() returns the report as Markdown; run.py saves it under data/reports/.
"""

from __future__ import annotations

import datetime as dt
from collections import Counter

from trader.store import Store, month_file


def render(store: Store, d: dt.date) -> str:
    day = d.isoformat()
    month = month_file(d, "jsonl")
    notebook = [r for r in store.records(f"notebook/{month}") if r["date"] == day]
    decisions = [r for r in notebook if r["type"] == "decision"]
    buys = [r for r in decisions if r["action"] == "buy"]
    sells = [r for r in decisions if r["action"] == "exit"]
    skips = [r for r in notebook if r["type"] == "skip"]
    review = next((r for r in notebook if r["type"] == "review"), None)
    results = [r for r in notebook if r["type"] == "result"]
    mood = next((r for r in store.records(f"analysis/{month}") if r["type"] == "mood" and r["date"] == day), {})
    snap = next((r for r in reversed(store.records_all("books")) if r["type"] == "snapshot" and r["date"] <= day), {})
    trust = next((r for r in reversed(store.records_all("trust")) if r["type"] == "trust" and r["date"] <= day), None)
    dont_know = [r for r in store.records(f"history/skipped/{month}") if r["date"] == day] if (store.history_dir / "skipped").exists() else []
    brake = buys[0]["brake"] if buys else next((r.get("brake") for r in reversed(notebook) if r["type"] == "run" and r.get("brake")), "normal")

    out = [f"# Trading plan — decided after the close on {d:%A %d %B %Y}", "",
           "Paper trading: these are the system's own decisions on fake money. It never places an order.", ""]
    if mood.get("mood") and mood["mood"] != "unknown":
        direction = "rising" if mood["dma50"] > mood["dma50_10_days_ago"] else "falling"
        out.append(f"**Market mood: {mood['mood']}.** Nifty 500 closed at {mood['index_close']:,.0f}; "
                   f"its 50-day average is {mood['dma50']:,.0f} and {direction}.")
    if snap:
        line = (f"**Account:** ₹{snap['balance_worse']:,.0f} (cautious figure)")
        if snap.get("gap"):
            line += f", up to ₹{snap['balance_better']:,.0f} depending on {snap['gap'] and 'unknown results'}"
        line += f". Highest so far ₹{snap['peak']:,.0f}. {len(snap['positions'])} open position(s)."
        out.append(line)
    out.append(f"**Losing-run brake:** {BRAKE.get(brake, brake)}")
    out.append("")

    out += ["## Orders for the next trading day", ""]
    if not buys and not sells:
        out += ["Nothing to do.", ""]
    if buys:
        out += ["### Buy at the open (place in the pre-open session, 9:00–9:08am)", "",
                "| Share | Qty | About | Stop | Target | Sell after | Confidence | Checklist |",
                "|---|---|---|---|---|---|---|---|"]
        for b in buys:
            conf = f"{b['confidence']:.0%}" if b.get("confidence") is not None else "—"
            out.append(f"| **{b['symbol']}** | {b['quantity']} | ₹{b['entry_estimate']:,.2f} | ₹{b['stop']:,.2f} | "
                       f"₹{b['target']:,.2f} | {b['max_hold_days']} days | {conf} | {_name(store, b['checklist'])} |")
        out.append("")
        out.append("Skip any buy that opens at or below its stop, or at or above its target.")
        out.append("Once bought, set a stop-loss and a target order (a GTT/OCO order at most brokers).")
        out.append("")
        for b in buys:
            out.append(f"**{b['symbol']}.** {b['reasons']}")
            if b.get("case"):
                out.append(f"> Claude: {b['case']}")
            if b.get("veto"):
                out.append(f"> **Claude objects** ({b['veto']['category'].replace('_', ' ')}): {b['veto']['reason']} "
                           "*Recorded, not obeyed, during paper trading.*")
            out.append("")
    if sells:
        out += ["### Sell at the open (time limit reached)", "", "| Share | Qty |", "|---|---|"]
        out += [f"| **{s['symbol']}** | {s['quantity']} |" for s in sells]
        out.append("")

    if snap.get("positions"):
        out += ["## Open positions: keep their exit orders in place", "",
                "| Share | Qty | Bought at | Stop | Target | Days held |", "|---|---|---|---|---|---|"]
        out += [f"| {p['symbol']} | {p['qty']} | ₹{p['entry']:,.2f} | ₹{p['stop']:,.2f} | ₹{p['target']:,.2f} | "
                f"{p['days']} of {p['max_hold']} |" for p in snap["positions"]]
        out.append("")

    if results:
        out += ["## Finished today", "", "| Share | How it ended | Result |", "|---|---|---|"]
        for r in results:
            if r["outcome"] == "exited":
                res = f"{r['gross_return_pct']:+.1f}%: {_times(r.get('r_multiple'))}"
            elif r["outcome"] == "unknown":
                res = (f"unknown: somewhere between {_times(r.get('r_multiple_worse'))} "
                       f"and {_times(r.get('r_multiple_better'))}")
            else:
                res = "not bought"
            out.append(f"| {r['symbol']} | {r['reason']} | {res} |")
        out.append("")

    if skips:
        out += ["## Candidates not taken", ""]
        out += [f"- {n} × {reason}" for reason, n in Counter(_short(s["reason"]) for s in skips).most_common()]
        out.append("")

    out += ["## Health", ""]
    review_line = {"accepted": "received and accepted", "missing": "did not arrive (decisions stand without it)",
                   "rejected": "rejected by the check: " + "; ".join((review or {}).get("problems", [])[:3])}
    if review:
        out.append(f"- Claude's review: {review_line[review['status']]}.")
    out.append(f"- Shares sitting out today (Clean could not verify them): {len(dont_know)}.")
    if trust:
        off = [f"{_name(store, k.split('|')[0])} in a {k.split('|')[1]} market" for k, c in trust["cells"].items() if c.get("switched_off")]
        overall = trust.get("calibration_overall") or {}
        out.append(f"- Trust scores: version {trust['version']}, from {trust['evidence_count']} finished trade(s).")
        if overall:
            out.append(f"- Confidence check: {overall['verdict']} (stated {overall['stated']:.0%}, "
                       f"happened {_pct(overall['happened'][0])}–{_pct(overall['happened'][1])}, over {overall['trades']} trades).")
        if off:
            out.append(f"- Switched off: {', '.join(off)}.")
        for s in trust.get("suggestions", []):
            out.append(f"- Suggestion for you to look at: {s}")
    out.append("")
    return "\n".join(out)


BRAKE = {
    "normal": "off.",
    "half": "on. The account is more than 10% below its highest, so each trade risks half the usual amount.",
    "paused": "on. The account fell more than 15% below its highest, so new buys are paused for 10 trading days.",
    "half after pause": "on. After a pause, each trade risks half the usual amount until the account is back within 10% of its highest.",
}


def _times(r) -> str:
    if r is None:
        return "—"
    return f"gained {r:.1f} times what it risked" if r >= 0 else f"lost {-r:.1f} times what it risked"


def _name(store: Store, cid: str) -> str:
    return store.checklists().get(cid, {}).get("name", cid)


def _short(reason: str) -> str:
    return reason.split(":")[0] if reason.startswith(("no room", "losing-run")) else reason


def _pct(x) -> str:
    return "—" if x is None else f"{x:.0%}"
