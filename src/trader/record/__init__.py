"""Record: writes every decision to the notebook before anything acts on it, and later its result.
Writes data/notebook/. Lines are only ever added; corrections are new entries pointing at old ones."""

from __future__ import annotations

import datetime as dt

from trader.store import Store


def write_run(store: Store, d: dt.date, stage: str, **facts) -> None:
    _write(store, d, [{"type": "run", "date": d.isoformat(), "stage": stage, "code_version": store.code_version(), **facts}])


def write_proposals(store: Store, d: dt.date, proposals: list[dict], skips: list[dict]) -> None:
    _write(store, d, [{"type": "proposal", **p} for p in proposals] + [{"type": "skip", **s} for s in skips])


def write_decisions(store: Store, d: dt.date, review: str) -> list[dict]:
    """Final decisions: today's proposals after Claude's review. Until M4 there is no review."""
    limits = store.config("limits")
    decisions = [{**{k: v for k, v in r.items() if k != "type"}, "type": "decision", "review": review, "limits": limits}
                 for r in store.records(f"notebook/{d.year}.jsonl") if r["type"] == "proposal" and r["date"] == d.isoformat()]
    _write(store, d, decisions)
    return decisions


def write_results(store: Store, d: dt.date) -> int:
    """A result for every trade that finished today, read from Settle's books."""
    decisions = {r["id"]: r for y in (d.year - 1, d.year) for r in store.records(f"notebook/{y}.jsonl")
                 if r["type"] == "decision" and r["action"] == "buy"}
    entries = {}
    results = []
    for r in store.records(f"books/{d.year}.jsonl"):
        if r["type"] != "event":
            continue
        if r["event"] == "entered":
            entries[r["id"]] = r
        if r["date"] != d.isoformat() or r["event"] not in ("exited", "unknown", "not_entered"):
            continue
        dec = decisions.get(r["id"], {})
        res = {"type": "result", "id": r["id"], "date": d.isoformat(), "symbol": r["symbol"],
               "checklist": dec.get("checklist"), "outcome": r["event"], "reason": r.get("reason")}
        entry = entries.get(r["id"]) or _entry_last_year(store, d, r["id"])
        if entry and r["event"] != "not_entered":
            price, risk = entry["price"], entry["price"] - dec["stop"]
            res.update(entry_price=price, quantity=entry["qty"])
            if r["event"] == "exited":
                res.update(exit_price=r["price"], gross_return_pct=round((r["price"] / price - 1) * 100, 3),
                           r_multiple=round((r["price"] - price) / risk, 3) if risk > 0 else None)
            else:
                res.update(exit_price_worse=r["worse"], exit_price_better=r["better"],
                           r_multiple_worse=round((r["worse"] - price) / risk, 3) if risk > 0 else None,
                           r_multiple_better=round((r["better"] - price) / risk, 3) if risk > 0 else None)
        results.append(res)
    _write(store, d, results)
    return len(results)


def _entry_last_year(store: Store, d: dt.date, id_: str) -> dict | None:
    for r in store.records(f"books/{d.year - 1}.jsonl"):
        if r["type"] == "event" and r["event"] == "entered" and r["id"] == id_:
            return r
    return None


def _write(store: Store, d: dt.date, records: list[dict]) -> None:
    if records:
        store.writer("record").append_records(f"{d.year}.jsonl", records)
