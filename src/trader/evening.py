"""The evening's jobs in order, shared by the live run, practice replays and the backtest,
so all three run exactly the same code (pass1 design: "the backtest runs the real jobs")."""

from __future__ import annotations

import datetime as dt

from trader import analyze, decide, learn, record, report, settle
from trader.store import Store


def evening_jobs(store: Store, view, balance: float, decide_today: bool):
    """The order every evening runs in (spec note: Settle and Learn before Decide)."""
    d = view.date
    settle.settle_day(store, view, balance)
    record.write_results(store, d)
    learn.learn_day(store, d)
    analyze.analyze_day(store, view)
    if not decide_today:
        return None
    proposals, skips, brake = decide.decide(store, view, learn.latest_version(store, d))
    record.write_proposals(store, d, proposals, skips)
    return proposals, brake



def replay(store: Store, start: dt.date, end: dt.date, quiet: bool = False, report_last: bool = False) -> None:
    """Every evening job over past trading days, without Claude's review (it would know the future)."""
    history = store.history()
    balance = store.config("limits")["paper_starting_balance_inr"]
    days = [d for d in history.calendar if start <= d <= end]
    for d in days:
        record.write_run(store, d, "start")
        proposals, brake = evening_jobs(store, history.as_of(d), balance, decide_today=True)
        record.write_run(store, d, "proposed", proposals=len(proposals), brake=brake["mode"])
        record.write_decisions(store, d, None, ["no review arrived"])
        record.write_run(store, d, "finalized")
        if not quiet:
            print(d, f"proposed {len(proposals)}", f"brake {brake['mode']}")
    if report_last and days:
        store.writer("report").add_file(f"{days[-1]:%Y-%m}/{days[-1].isoformat()}.md", report.render(store, days[-1]).encode())
