"""Watchers: the daily report. Read-only: nothing in the system reads what it produces.

Written for someone who is not a trader: every number comes with what it means and what
to do about it. render() returns Markdown; run.py saves it under data/reports/.
"""

from __future__ import annotations

import csv
import datetime as dt
from collections import Counter

from trader.analyze.conditions import BASIC_CHECKS, explain
from trader.store import Store, month_file

GUIDE = "../../../docs/how-to-read-the-daily-report.md"


def render(store: Store, d: dt.date) -> str:
    day = d.isoformat()
    month = month_file(d, "jsonl")
    notebook = [r for r in store.records(f"notebook/{month}") if r["date"] == day]
    everything = store.records_all("notebook")
    decided = {r["id"]: r for r in everything if r["type"] == "decision" and r["action"] == "buy"}
    buys = [r for r in notebook if r["type"] == "decision" and r["action"] == "buy"]
    sells = [r for r in notebook if r["type"] == "decision" and r["action"] == "exit"]
    skips = [r for r in notebook if r["type"] == "skip"]
    review = next((r for r in notebook if r["type"] == "review"), None)
    results = [r for r in notebook if r["type"] == "result"]
    mood = next((r for r in store.records(f"analysis/{month}") if r["type"] == "mood" and r["date"] == day), {})
    snap = next((r for r in reversed(store.records_all("books")) if r["type"] == "snapshot" and r["date"] <= day), {})
    trust = next((r for r in reversed(store.records_all("trust")) if r["type"] == "trust" and r["date"] <= day), None)
    dont_know = [r for r in store.records(f"history/skipped/{month}") if r["date"] == day]
    checklists = store.checklists()
    cal = _Calendar(store, d)
    selling = {s["id"] for s in sells}
    running = [p for p in snap.get("positions", []) if p["id"] not in selling]
    tomorrow = cal.after(d, 1)

    out = [f"# Your trading plan for {_day(tomorrow)}", "",
           f"Decided after the market closed on {_day(d)}. This is **practice with fake money**: the system never places "
           "orders. If you want to follow along, place them yourself. New to this? See "
           f"[how to read this report]({GUIDE}).", ""]

    # In short
    out += ["## In short", ""]
    short = []
    if buys:
        short.append(f"**Buy** tomorrow morning: {_list([b['symbol'] for b in buys])}.")
    if sells:
        short.append(f"**Sell** tomorrow morning: {_list([s['symbol'] for s in sells])} "
                     f"({'its' if len(sells) == 1 else 'their'} time is up).")
    if running:
        short.append(f"**Still running**, nothing to do: {_list([p['symbol'] for p in running])}.")
    ended = [r for r in results if r["outcome"] != "not_entered"]
    if ended:
        short.append(f"**Ended today:** {_list([r['symbol'] for r in ended])}.")
    if not short:
        short.append("Nothing to do tomorrow.")
    out += [f"- {line}" for line in short] + [""]

    # 1. Buys
    if buys:
        out += ["## 1. Buy tomorrow morning", "",
                "**How:** place a buy order \"at market\" in the pre-open session (9:00–9:08am), so you get the opening price. "
                "**Don't buy** if the share opens at or below its stop-loss, or at or above its target: the plan no longer makes sense.", ""]
        for b in buys:
            out += _buy(b, checklists, cal, d)

    # 2. Sells
    if sells:
        out += ["## 2. Sell tomorrow morning", ""]
        for s in sells:
            p = next((x for x in snap.get("positions", []) if x["id"] == s["id"]), {})
            why = decided.get(s["id"], {})
            name = checklists.get(why.get("checklist"), {}).get("name", "a checklist")
            bought = dt.date.fromisoformat(p["entered"]) if p.get("entered") else None
            out += [f"### {s['symbol']}: sell all {s['quantity']} shares at the open", ""]
            out.append(f"Bought on {_day(bought)} at ₹{p.get('entry', 0):,.2f}, because it matched **{name}**. "
                       f"In {p.get('max_hold', 3)} trading days it reached neither its target (₹{p.get('target', 0):,.2f}) "
                       f"nor its stop-loss (₹{p.get('stop', 0):,.2f}).")
            out.append("")
            out.append("**Why sell now:** these trades bet on a move within a few days. If it hasn't come by now, the idea "
                       "hasn't worked, so the plan takes whatever the price is and frees the money for new trades. "
                       "**First cancel** its stop-loss and target orders, then sell at the open.")
            out.append("")

    # 3. Running
    if running:
        out += ["## 3. Trades still running: nothing to do", "",
                "These trades are under way. If you are following along, just check that each one's stop-loss and target "
                "orders are still active with your broker. Each ends at its stop-loss, its target, or its last day, "
                "whichever comes first.", "",
                "| Share | Shares | Bought | Price paid | Stop-loss | Target | If neither, sell at the open on |",
                "|---|---|---|---|---|---|---|"]
        for p in running:
            entered = dt.date.fromisoformat(p["entered"])
            last = cal.after(entered, p["max_hold"])
            out.append(f"| {p['symbol']} | {p['qty']} | {_day(entered, short=True)} | ₹{p['entry']:,.2f} | "
                       f"₹{p['stop']:,.2f} | ₹{p['target']:,.2f} | {_day(last, short=True)} |")
        out.append("")

    # 4. Ended
    if results:
        out += ["## 4. Trades that ended today", ""]
        for r in results:
            out.append("- " + _ended(r))
        out.append("")

    # 5. Others
    if skips:
        out += ["## 5. Other shares that qualified but weren't picked", ""]
        reasons = Counter(_why_skipped(s["reason"]) for s in skips)
        out.append(f"{len(skips)} more share(s) met a checklist today but weren't picked:")
        out += [f"- {n} because {reason}" for reason, n in reasons.most_common()]
        out.append("")

    # 6. Account and market
    out += ["## 6. The practice account and the market", ""]
    if snap:
        start = store.config("limits")["paper_starting_balance_inr"]
        line = (f"**Balance: ₹{snap['balance_worse']:,.0f}** (started at ₹{start:,.0f}; highest so far ₹{snap['peak']:,.0f}). "
                "This counts open trades at today's closing prices.")
        if snap.get("gap"):
            line += (f" Some past results couldn't be settled from daily prices, so the true figure could be up to "
                     f"₹{snap['balance_better']:,.0f}; the system always plans with the lower one.")
        out.append(line)
        out.append("")
    brake = (buys[0].get("brake") if buys else None) or next(
        (r.get("brake") for r in reversed(notebook) if r["type"] == "run" and r.get("brake")), "normal")
    out.append(f"**Losing-run brake: {BRAKE.get(brake, brake)}")
    out.append("")
    if mood.get("mood") and mood["mood"] != "unknown":
        out.append(f"**Market mood: {MOOD[mood['mood']]}** The Nifty 500 index (a measure of the whole market) closed at "
                   f"{mood['index_close']:,.0f}, against its 50-day average of {mood['dma50']:,.0f}, which is "
                   f"{'rising' if mood['dma50'] > mood['dma50_10_days_ago'] else 'falling'}. The system tracks how each "
                   "checklist does in each mood.")
        out.append("")

    # 7. Health
    out += ["## 7. Is the system working properly?", ""]
    day_failed = [r for r in dont_know if r["symbol"] == "*"]
    shares_out = [r for r in dont_know if r["symbol"] != "*"]
    if day_failed:
        out.append(f"- ⚠️ **Market data:** today's NSE file couldn't be read ({day_failed[0]['reason']}).")
    else:
        out.append(f"- {'✅' if not shares_out else '⚠️'} **Market data:** "
                   + ("complete." if not shares_out else f"{len(shares_out)} share(s) left out today because their figures couldn't be verified."))
    if review:
        ok = review["status"] == "accepted"
        text = {"accepted": "arrived and passed the checks.",
                "missing": "didn't arrive. The trades above stand without it.",
                "rejected": "arrived but failed the checks, so it was set aside. The trades above stand without it."}
        out.append(f"- {'✅' if ok else '⚠️'} **Claude's review:** {text[review['status']]}")
    if trust and trust.get("calibration_overall"):
        c = trust["calibration_overall"]
        lo, hi = c["happened"]
        happened = f"{lo:.0%}" if f"{lo:.0%}" == f"{hi:.0%}" else f"{lo:.0%}–{hi:.0%}"
        mark = "✅" if c["verdict"] in ("honest", "not enough trades yet") else "⚠️"
        out.append(f"- {mark} **Honesty check:** when the system said about {c['stated']:.0%}, {happened} of its trades "
                   f"made money ({c['trades']} trades so far): {c['verdict']}.")
    if trust:
        for key, cell in trust["cells"].items():
            if cell.get("switched_off"):
                cid, m = key.split("|")
                out.append(f"- ⚠️ **{checklists.get(cid, {}).get('name', cid)} is switched off when the market is "
                           f"{MOOD_WORD[m]}**: its trades in that mood lost money even counted generously, so it is skipped then.")
        for s in trust.get("suggestions", []):
            out.append(f"- 💡 **For you to look at:** {s}")
    out.append("")
    return "\n".join(out)


def _buy(b: dict, checklists: dict, cal: _Calendar, d: dt.date) -> list[str]:
    c = checklists.get(b["checklist"], {})
    f = b.get("figures", {})
    qty, price = b["quantity"], b["entry_estimate"]
    win, loss = qty * (b["target"] - price), qty * (price - b["stop"])
    first = cal.after(d, 1)
    last = cal.after(d, b["max_hold_days"])
    sell_on = cal.after(d, b["max_hold_days"] + 1)
    lines = [f"### {b['symbol']}: buy {qty} share{'s' if qty > 1 else ''} (about ₹{qty * price:,.0f})", "",
             f"**Why this share.** It matched the **{c.get('name', b['checklist'])}** checklist. {c.get('idea', '').strip()} "
             "All of its conditions were true today:", ""]
    for cond in c.get("conditions", []):
        (name, params), = cond.items()
        lines.append(f"- ✅ {explain(name, params, f)}")
    lines += ["", BASIC_CHECKS, "",
              "**The plan for this trade.**", "",
              "| | Price | What happens |", "|---|---|---|",
              f"| Buy | about ₹{price:,.2f} | at the open on {_day(first)} |",
              f"| Target | ₹{b['target']:,.2f} | sell to take the profit: about **+₹{win:,.0f}** |",
              f"| Stop-loss | ₹{b['stop']:,.2f} | sell to limit the loss: about **−₹{loss:,.0f}** |",
              f"| Time limit | — | if neither happens by the close on {_day(last)}, sell at the open on {_day(sell_on)} |", "",
              "After buying, place the stop-loss and the target with your broker as one order (called GTT-OCO at most "
              "brokers): whichever price is reached first sells the shares and cancels the other.", ""]
    if b.get("confidence") is not None:
        exp = b.get("expected_r", 0) * b.get("risk_amount", 0)
        if exp >= 1:
            verdict = f"so on average the system expects about +₹{exp:,.0f} from a trade like this."
        elif exp > -1:
            verdict = "but on its record so far, trades like this roughly break even on average."
        else:
            verdict = f"but on its record so far, trades like this lose about ₹{-exp:,.0f} on average."
        lines.append(f"**How likely.** About {b['confidence']:.0%} of similar trades made money. A win here (+₹{win:,.0f}) "
                     f"is bigger than a loss (−₹{loss:,.0f}), {verdict}")
    else:
        lines.append("**How likely.** Not measured yet: this kind of trade has no track record so far.")
    lines.append("")
    lines.append(f"**Why {qty} share{'s' if qty > 1 else ''}.** " + LIMIT_WORDS.get(b.get("size_limited_by"), ""))
    lines.append("")
    if b.get("case"):
        lines += [f"**Claude's view.** {b['case']}", ""]
    if b.get("veto"):
        lines += [f"**Claude objects** ({b['veto']['category'].replace('_', ' ')}): {b['veto']['reason']} "
                  "During practice the trade goes ahead anyway, so the record can show whether Claude's objections are right.", ""]
    return lines


def _ended(r: dict) -> str:
    sym = r["symbol"]
    if r["outcome"] == "not_entered":
        return f"**{sym}:** never bought. {NOT_BOUGHT.get(r['reason'], r['reason'])}."
    cost = r["entry_price"] * r["quantity"]
    if r["outcome"] == "unknown":
        return (f"**{sym}:** the day's prices touched both its stop-loss and its target, and daily prices can't say which "
                "came first. The system records it as unknown rather than guess.")
    rupees = r["gross_return_pct"] / 100 * cost
    how = ENDED.get(r["reason"], r["reason"])
    return (f"**{sym}:** {how}. Bought at ₹{r['entry_price']:,.2f}, sold at ₹{r['exit_price']:,.2f}: "
            f"**{'+' if rupees >= 0 else '−'}₹{abs(rupees):,.0f}** ({r['gross_return_pct']:+.1f}%).")


class _Calendar:
    """Trading days after a date: weekdays, minus NSE's holiday list when it is known."""

    def __init__(self, store: Store, d: dt.date):
        path = store.history_dir / "holidays.csv"
        self.holidays = set()
        if path.exists():
            with open(path, newline="") as f:
                self.holidays = {dt.date.fromisoformat(r["date"]) for r in csv.DictReader(f)}

    def after(self, d: dt.date | None, n: int) -> dt.date | None:
        if d is None:
            return None
        while n > 0:
            d += dt.timedelta(days=1)
            if d.weekday() < 5 and d not in self.holidays:
                n -= 1
        return d


BRAKE = {
    "normal": "off.** Each trade risks the usual amount (1% of the account).",
    "half": "on.** The account is more than 10% below its highest, so each trade risks half the usual amount.",
    "paused": "on.** The account fell more than 15% below its highest, so no new buys for 10 trading days.",
    "half after pause": "on.** After a pause, each trade risks half the usual amount until the account is back within 10% of its highest.",
}
MOOD = {"up": "rising.", "down": "falling.", "sideways": "mixed."}
MOOD_WORD = {"up": "rising", "down": "falling", "sideways": "mixed"}
LIMIT_WORDS = {
    "max position size": "That is the most your limits allow in one share (20% of the account).",
    "risk per trade": "That keeps the loss at the stop-loss within your limit for one trade (1% of the account, halved while the brake is on).",
    "max total open risk": "That keeps the loss, if every open trade hit its stop-loss at once, within your limit (5% of the account).",
    "cash on hand": "That is all the spare cash left after the other trades.",
}
ENDED = {
    "stop": "it fell to its stop-loss, which sold it",
    "target": "it rose to its target, which sold it",
    "time limit": "its 3 days were up, so it was sold at the open",
    "gapped through the stop": "it opened below its stop-loss (usually overnight news), so it sold at the open, for more than the planned loss",
    "gapped through the target": "it opened above its target, so it sold at the open, for more than the planned gain",
}
NOT_BOUGHT = {
    "opened beyond its exit": "It opened beyond its stop-loss or target, so the buy was cancelled",
    "could not trade": "It was stuck at its daily price limit, so nobody could buy it",
    "no price for 5 trading days": "There was no price for it for 5 trading days (trading may have been suspended)",
    "not enough cash": "There wasn't enough cash left",
}


def _why_skipped(reason: str) -> str:
    if reason.startswith("no room"):
        return "the account already holds or is buying 5 shares, the most your limits allow at once"
    if reason.startswith("cannot afford"):
        return "even one share would cost more than your limits allow in one share"
    if reason.startswith("already"):
        return "the account already holds it"
    if "switched off" in reason:
        return "its checklist is switched off in this market mood"
    if reason.startswith("losing-run brake"):
        return "the losing-run brake has paused new buys"
    return reason


def _day(d: dt.date | None, short: bool = False) -> str:
    if d is None:
        return "—"
    return f"{d:%a} {d.day} {d:%b}" if short else f"{d:%A} {d.day} {d:%B} {d.year}"


def _list(items: list[str]) -> str:
    return ", ".join(items[:-1]) + (" and " if len(items) > 1 else "") + items[-1] if items else ""
