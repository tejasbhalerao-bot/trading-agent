"""The evening run's second part: Claude's review, decisions, the report, and running twice."""

from __future__ import annotations

import json

import pytest

from trader import record
from trader.run import evening_jobs, finalize, replay
from trader.store import Store

from ..market import make_market


@pytest.fixture
def proposed(tmp_path):
    """A store whose last day has proposals but no decisions yet, as after `propose`."""
    days = make_market(tmp_path / "m", n_days=120)
    store = Store(tmp_path / "run", history_from=tmp_path / "m")
    replay(store, days[65], days[-2], quiet=True)
    today = days[-1]
    proposals, brake = evening_jobs(store, store.history().as_of(today), 10_000, decide_today=True)
    record.write_run(store, today, "proposed", proposals=len(proposals), brake=brake["mode"])
    buys = [p for p in proposals if p["action"] == "buy"]
    assert buys, "the test market should propose at least one buy"
    return store, today, buys


def test_an_accepted_review_is_attached_and_a_veto_is_recorded_but_not_obeyed(proposed):
    store, today, buys = proposed
    review = {"date": today.isoformat(), "reviews": [
        {"id": buys[0]["id"], "case": "Clean break on heavy volume.",
         "veto": {"category": "event", "reason": "Quarterly results are due within the holding period."}}]}
    finalize(store, today, do_publish=False, review_raw=json.dumps(review).encode())
    decisions = [r for r in store.records_all("notebook") if r["type"] == "decision" and r["date"] == today.isoformat()]
    first = next(r for r in decisions if r["id"] == buys[0]["id"])
    assert first["case"] == "Clean break on heavy volume."
    assert first["veto"]["category"] == "event" and first["veto_obeyed"] is False
    assert len([r for r in decisions if r["action"] == "buy"]) == len(buys)   # the vetoed trade is still taken


def test_a_bad_review_is_set_aside_and_the_evening_carries_on(proposed):
    store, today, buys = proposed
    bad = {"date": today.isoformat(), "reviews": [{"id": "2000-01-01/ZZZ/x", "case": "invented"}]}
    finalize(store, today, do_publish=False, review_raw=json.dumps(bad).encode())
    review = next(r for r in store.records_all("notebook") if r["type"] == "review" and r["date"] == today.isoformat())
    assert review["status"] == "rejected"
    assert len([r for r in store.records_all("notebook") if r["type"] == "decision" and r["action"] == "buy"
                and r["date"] == today.isoformat()]) == len(buys)


def test_the_report_is_written_after_the_decisions_and_finalize_runs_once(proposed):
    store, today, _ = proposed
    finalize(store, today, do_publish=False, review_raw=None)
    report = store.data / "reports" / f"{today:%Y-%m}" / f"{today.isoformat()}.md"
    assert report.exists() and "Trading plan" in report.read_text()
    stages = [r["stage"] for r in store.records_all("notebook") if r["type"] == "run" and r["date"] == today.isoformat()]
    assert stages.index("decided") < stages.index("finalized")
    assert finalize(store, today, do_publish=False) == "already finalized today"
