"""The one entry point the daily GitHub Actions workflows run.

    python3 src/trader/run.py propose  [--date YYYY-MM-DD] [--no-publish]
        Evening, part 1: fetch (catching up missed days), clean, settle, learn, analyze, decide.
    python3 src/trader/run.py finalize [--date YYYY-MM-DD] [--no-publish]
        Evening, part 2: check Claude's review, record the decisions, write the daily report.
    python3 src/trader/run.py backfill FROM TO
        Fetch and clean past days into data/history.
    python3 src/trader/run.py replay FROM TO --into DIR [--report]
        Run the trading jobs over past days into DIR (practice; never the real record).
    python3 src/trader/run.py backtest FROM TO --work DIR
        Replay the period in DIR, then write results and starting trust scores to data/backtest.

Both evening parts are safe to run more than once: a part already done for the day exits.
Timetable and platform limits: docs/design/constraints.md.
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO / "src"))

from trader import clean, fetch, record, report  # noqa: E402
from trader.evening import evening_jobs, replay  # noqa: E402
from trader.clean import parse  # noqa: E402
from trader.schema.review import check_review  # noqa: E402
from trader.store import Store, month_file  # noqa: E402
from trader.store.publish import publish, read_from_branch  # noqa: E402

IST = dt.timezone(dt.timedelta(hours=5, minutes=30))
LAST_TRY = dt.time(21, 0)  # after this, a missing price file means the day failed (or the market was closed)
REVIEW_FILE = "work/review.json"


def propose(store: Store, today: dt.date, now: dt.datetime, do_publish: bool = True) -> str:
    if _stage(store, today, "proposed"):
        return "already proposed today"
    _finalize_leftover(store, today, do_publish)
    cleaner = clean.Cleaner(store)
    ref = fetch.fetch_reference(store, today)
    if ref["symbol_changes"]:
        cleaner.add_renames(ref["symbol_changes"], today)
    if ref["holidays"]:
        cleaner.add_holidays(ref["holidays"])
    closed = "market closed: NSE holiday" if ref["holidays"] and today in parse.holidays(ref["holidays"]) else None
    actions = fetch.fetch_corporate_actions(store, today - dt.timedelta(days=30), today + dt.timedelta(days=30), on=today)
    if actions:
        cleaner.add_announcements(actions, seen=today, backfill=False)

    d = (cleaner.prev_day + dt.timedelta(days=1)) if cleaner.prev_day else today
    while d <= today and not (d == today and closed):
        got = fetch.fetch_day(store, d, historical=d < today)
        if got.status == "delivered":
            cleaner.clean_day(d, got.files["price_file"], got.files.get("index_closes"))
        elif d == today:
            if now.time() < LAST_TRY:
                # Nothing is published, so the next run starts again from the same place.
                return "today's file is not published yet; a later run will retry"
            closed = "market closed: no file on a weekend" if today.weekday() >= 5 else "failed: no price file by 9pm"
        d += dt.timedelta(days=1)

    history = store.history()
    # Days needing the evening jobs come from the notebook's own record, not from Clean's state,
    # so a day cleaned in an earlier, interrupted run is never skipped.
    done = [r["date"] for r in store.records_all("notebook") if r["type"] == "run" and r["stage"] in ("proposed", "caught up")]
    last_done = max(done) if done else None
    new_days = [x for x in history.calendar if x <= today and (last_done is None or x.isoformat() > last_done)]
    if last_done is None:
        new_days = new_days[-1:]  # first ever evening: start today, not from the beginning of history
    balance = store.config("limits")["paper_starting_balance_inr"]
    summary = ""
    for d in new_days:
        record.write_run(store, d, "start")
        out = evening_jobs(store, history.as_of(d), balance, decide_today=d == today and not closed)
        if d == today and not closed:
            proposals, brake = out
            record.write_run(store, d, "proposed", proposals=len(proposals), brake=brake["mode"])
            summary = f"proposed {len(proposals)} order(s)"
        else:
            record.write_run(store, d, "caught up", note="missed evening: settled and learned; no decisions, "
                             "since orders cannot be placed in the past")
    if closed:
        return _close(store, today, closed, do_publish)
    _publish(store, today, "proposed", do_publish)
    return summary


def finalize(store: Store, today: dt.date, do_publish: bool = True, review_raw: bytes | None = None,
             late: bool = False) -> str:
    if _stage(store, today, "finalized"):
        return "already finalized today"
    if not _stage(store, today, "proposed"):
        return "nothing to finalize: no proposals today"
    if review_raw is None:
        review_raw = read_from_branch(store.repo_root, f"claude/review-{today.isoformat()}", REVIEW_FILE)
    ids = {p["id"] for p in record.proposals_for(store, today) if p["action"] == "buy"}
    review, problems = check_review(review_raw, today.isoformat(), ids)
    record.write_decisions(store, today, review, problems)
    record.write_run(store, today, "decided", review="accepted" if review else problems[0][:80], late=late)
    _publish(store, today, "decisions", do_publish)       # decisions are saved before the report exists
    store.writer("report").add_file(f"{today:%Y-%m}/{today.isoformat()}.md", report.render(store, today).encode())
    record.write_run(store, today, "finalized")
    _publish(store, today, "report", do_publish)
    return f"finalized; review {'accepted' if review else 'not used: ' + problems[0]}"


def backfill(store: Store, start: dt.date, end: dt.date) -> None:
    """Fetch and Clean every day in the range, oldest first. Weekends too: NSE holds occasional
    weekend sessions (e.g. Budget day), and a missing file simply means the market was closed."""
    cleaner = clean.Cleaner(store)
    lo = start - dt.timedelta(days=30)
    while lo <= end + dt.timedelta(days=30):  # one year per request
        hi = min(lo + dt.timedelta(days=365), end + dt.timedelta(days=30))
        actions = fetch.fetch_corporate_actions(store, lo, hi, on=start)
        if actions is None:
            raise SystemExit(f"could not fetch corporate actions {lo}..{hi}; nothing cleaned")
        print(f"corporate actions {lo}..{hi}: {cleaner.add_announcements(actions, seen=start, backfill=True)} new")
        lo = hi + dt.timedelta(days=1)
    d = start
    while d <= end:
        if cleaner.prev_day is None or d > cleaner.prev_day:
            got = fetch.fetch_day(store, d, historical=True)
            if got.status == "delivered":
                print(d, cleaner.clean_day(d, got.files["price_file"], got.files.get("index_closes")))
            else:
                print(d, got.status)
        d += dt.timedelta(days=1)


def _stage(store: Store, d: dt.date, stage: str) -> bool:
    return any(r["type"] == "run" and r["date"] == d.isoformat() and r["stage"] == stage
               for r in store.records(f"notebook/{month_file(d, 'jsonl')}"))


def _finalize_leftover(store: Store, today: dt.date, do_publish: bool) -> None:
    """If an earlier evening proposed but never finalized (both finalize runs lost), finish it now."""
    runs = [r for r in store.records_all("notebook") if r["type"] == "run" and r["date"] < today.isoformat()]
    proposed = [r["date"] for r in runs if r["stage"] == "proposed"]
    if proposed and not any(r["date"] == proposed[-1] and r["stage"] == "finalized" for r in runs):
        finalize(store, dt.date.fromisoformat(proposed[-1]), do_publish, late=True)


def _close(store: Store, d: dt.date, reason: str, do_publish: bool) -> str:
    record.write_run(store, d, "closed", reason=reason)
    _publish(store, d, "closed", do_publish)
    return reason


def _publish(store: Store, d: dt.date, what: str, do_publish: bool) -> None:
    if do_publish:
        print(f"published {publish(store.repo_root, f'Evening run {d.isoformat()}: {what}') or 'nothing'}")


def main(argv: list[str]) -> int:
    flags = {a for a in argv if a.startswith("--")}
    date = next((argv[i + 1] for i, a in enumerate(argv) if a == "--date"), None)
    now = dt.datetime.now(IST)
    today = dt.date.fromisoformat(date) if date else now.date()
    if date:
        now = dt.datetime.combine(today, dt.time(23, 59), IST)
    if argv[:1] == ["propose"]:
        print(propose(Store(REPO), today, now, do_publish="--no-publish" not in flags))
        return 0
    if argv[:1] == ["finalize"]:
        print(finalize(Store(REPO), today, do_publish="--no-publish" not in flags))
        return 0
    if argv[:1] == ["backfill"] and len(argv) == 3:
        backfill(Store(REPO), dt.date.fromisoformat(argv[1]), dt.date.fromisoformat(argv[2]))
        return 0
    if argv[:1] == ["backtest"] and len(argv) >= 5 and argv[3] == "--work":
        from trader.backtest import run_backtest
        start, end = dt.date.fromisoformat(argv[1]), dt.date.fromisoformat(argv[2])
        out = run_backtest(Store(REPO), Path(argv[4]), start, end, f"bt-{now.date().isoformat()}")
        print(f"{out['trades']} trades settled; account: {out['portfolio']}")
        return 0
    if argv[:1] == ["replay"] and len(argv) >= 5 and argv[3] == "--into":
        replay(Store(argv[4], history_from=REPO), dt.date.fromisoformat(argv[1]), dt.date.fromisoformat(argv[2]),
               report_last="--report" in flags)
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
