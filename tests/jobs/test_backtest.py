"""The backtest: it runs the real jobs, judges every candidate, and its starting scores reach Learn."""

from __future__ import annotations

import datetime as dt

import pytest

from trader import learn
from trader.backtest import COSTS, _returns, run_backtest
from trader.store import Store, month_file

from ..market import make_market


@pytest.fixture
def backtest(tmp_path):
    days = make_market(tmp_path / "m", n_days=130)
    repo = Store(tmp_path / "repo", history_from=tmp_path / "m")
    out = run_backtest(repo, tmp_path / "work", days[65], days[-1], "bt-test")
    return repo, Store(tmp_path / "work", history_from=tmp_path / "m"), out


def test_every_settled_candidate_is_judged_taken_or_not(backtest):
    repo, work, out = backtest
    settled = [e for e in work.records_all("books") if e["type"] == "event"
               and e["event"] in ("exited", "unknown", "shadow_exited", "shadow_unknown")]
    assert out["trades"] == len(settled) > 0
    trades = [r for r in repo.records_all("backtest/trades")]
    assert {t["taken"] for t in trades} == {True, False}


def test_results_are_given_under_every_cost_assumption(backtest):
    _, _, out = backtest
    overall = {s["costs"]: s for s in out["stats"] if s["level"] == "all"}
    assert set(overall) == set(COSTS)
    assert overall["none"]["avg_return_pct"][0] > overall["taxes_and_fees"]["avg_return_pct"][0] > overall["with_flat_fees"]["avg_return_pct"][0]


def test_costs_come_off_every_trade():
    t = {"entry": 100.0, "stop": 98.0, "exit": 103.0, "outcome": "exited"}
    lo, hi, r = _returns(t, 0.25)
    assert (round(lo, 2), round(hi, 2), round(r, 3)) == (2.75, 2.75, 1.375)


def test_learn_starts_from_the_backtest(backtest, tmp_path):
    repo, _, _ = backtest
    d = dt.date(2026, 1, 5)
    repo.writer("record").append_records(month_file(d, "jsonl"), [
        {"type": "decision", "action": "buy", "id": "x", "checklist": "quiet-breakout-v1", "mood": "up",
         "stop": 95, "confidence": 0.5, "date": d.isoformat()},
        {"type": "result", "id": "x", "date": d.isoformat(), "outcome": "exited", "r_multiple": 1.5, "entry_price": 100}])
    v = learn.learn_day(repo, d)
    assert v["backtest_run"] == "bt-test"
    assert v["overall"]["backtest_trades"] > 0
