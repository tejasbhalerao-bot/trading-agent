"""Record: writes every decision to the notebook before anything acts on it, and later its result.
Writes data/notebook/. Lines are only ever added; corrections are new entries pointing at old ones."""

from __future__ import annotations

import datetime as dt

from trader.store import Store, month_file


def write_run(store: Store, d: dt.date, stage: str, **facts) -> None:
    _write(store, d, [{"type": "run", "date": d.isoformat(), "stage": stage, "code_version": store.code_version(), **facts}])


def write_proposals(store: Store, d: dt.date, proposals: list[dict], skips: list[dict]) -> None:
    _write(store, d, [{"type": "proposal", **p} for p in proposals] + [{"type": "skip", **s} for s in skips])


def proposals_for(store: Store, d: dt.date) -> list[dict]:
    return [r for r in store.records(f"notebook/{month_file(d, 'jsonl')}") if r["type"] == "proposal" and r["date"] == d.isoformat()]


def write_decisions(store: Store, d: dt.date, review: dict | None, problems: list[str]) -> list[dict]:
    """Final decisions: today's proposals, with Claude's review attached.

    During paper trading a veto is recorded but not obeyed: the trade is taken anyway,
    so the record can show whether Claude's objections were right (M1 decision).
    """
    status = "accepted" if review else ("missing" if problems == ["no review arrived"] else "rejected")
    by_id = {r["id"]: r for r in (review or {}).get("reviews", [])}
    limits = store.config("limits")
    entries = [{"type": "review", "date": d.isoformat(), "status": status, "problems": problems,
                "reviews": list(by_id.values())}]
    for p in proposals_for(store, d):
        r = by_id.get(p["id"], {})
        entries.append({**{k: v for k, v in p.items() if k != "type"}, "type": "decision", "limits": limits,
                        "review_status": status, "case": r.get("case"), "veto": r.get("veto"),
                        "veto_obeyed": False if r.get("veto") else None})
    _write(store, d, entries)
    return entries[1:]


def write_results(store: Store, d: dt.date) -> int:
    """A result for every trade that finished today, read from Settle's books."""
    decisions = {r["id"]: r for r in store.records_all("notebook") if r["type"] == "decision" and r["action"] == "buy"}
    entries = {}
    results = []
    for r in store.records_all("books"):
        if r["type"] != "event":
            continue
        if r["event"] == "entered":
            entries[r["id"]] = r
        if r["date"] != d.isoformat() or r["event"] not in ("exited", "unknown", "not_entered"):
            continue
        dec = decisions.get(r["id"], {})
        res = {"type": "result", "id": r["id"], "date": d.isoformat(), "symbol": r["symbol"],
               "checklist": dec.get("checklist"), "outcome": r["event"], "reason": r.get("reason")}
        entry = entries.get(r["id"])
        if entry and r["event"] != "not_entered":
            price = entry["price"]
            res.update(entry_price=price, quantity=entry["qty"])
            if r["event"] == "exited":
                same_terms_entry = r.get("entry", price)  # after a split, the entry in post-split terms
                res.update(exit_price=r["price"], gross_return_pct=round((r["price"] / same_terms_entry - 1) * 100, 3),
                           r_multiple=r.get("r_multiple"))
            else:
                res.update(exit_price_worse=r["worse"], exit_price_better=r["better"],
                           r_multiple_worse=r.get("r_multiple_worse"), r_multiple_better=r.get("r_multiple_better"))
        results.append(res)
    _write(store, d, results)
    return len(results)


def _write(store: Store, d: dt.date, records: list[dict]) -> None:
    if records:
        store.writer("record").append_records(month_file(d, "jsonl"), records)
