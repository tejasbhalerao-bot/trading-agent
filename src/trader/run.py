"""The one entry point the daily GitHub Actions workflows run.

    python3 src/trader/run.py backfill FROM TO          fetch and clean past days into data/history
    python3 src/trader/run.py replay FROM TO --into DIR run the trading jobs over past days into DIR (practice)
    python3 src/trader/run.py probe                     M0 data check (throwaway; replaced by Fetch)

Dates are YYYY-MM-DD. The evening run (propose / finalize) arrives in M4.
"""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if __package__ in (None, ""):
    sys.path.insert(0, str(REPO / "src"))

from trader import analyze, clean, decide, fetch, record, settle  # noqa: E402
from trader.fetch import probe  # noqa: E402
from trader.store import Store  # noqa: E402
from trader.store.publish import publish  # noqa: E402


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


def replay(store: Store, start: dt.date, end: dt.date, quiet: bool = False) -> None:
    """Settle, Record, Analyze, Decide and Record again, for each trading day in the range (no review)."""
    history = store.history()
    balance = store.config("limits")["paper_starting_balance_inr"]
    for d in history.calendar:
        if not start <= d <= end:
            continue
        view = history.as_of(d)
        record.write_run(store, d, "start")
        s = settle.settle_day(store, view, balance)
        n_results = record.write_results(store, d)
        a = analyze.analyze_day(store, view)
        proposals, skips = decide.decide(store, view)
        record.write_proposals(store, d, proposals, skips)
        record.write_decisions(store, d, review="none (no review until M4)")
        record.write_run(store, d, "end", proposals=len(proposals), skips=len(skips), results=n_results)
        if not quiet:
            print(d, a["mood"], f"matches {a['matches']}", f"proposed {len(proposals)}", f"open {s['open']}")


def cmd_probe(no_publish: bool = False) -> int:
    report = probe.run()
    print(probe.summary(report))
    stamp = report["probed_at"].replace(":", "").replace("+0000", "Z")
    path = Store(REPO).writer("fetch").add_file(f"_probe/{stamp}.json", (json.dumps(report, indent=2) + "\n").encode())
    print(f"recorded {path.relative_to(REPO)}")
    if not no_publish:
        print(f"published {publish(REPO, f'M0 data check {stamp}') or 'nothing'}")
    return 0


def main(argv: list[str]) -> int:
    if argv[:1] == ["probe"]:
        return cmd_probe(no_publish="--no-publish" in argv)
    if argv[:1] == ["backfill"] and len(argv) == 3:
        backfill(Store(REPO), dt.date.fromisoformat(argv[1]), dt.date.fromisoformat(argv[2]))
        return 0
    if argv[:1] == ["replay"] and len(argv) == 5 and argv[3] == "--into":
        replay(Store(argv[4], history_from=REPO), dt.date.fromisoformat(argv[1]), dt.date.fromisoformat(argv[2]))
        return 0
    print(__doc__)
    return 2


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
