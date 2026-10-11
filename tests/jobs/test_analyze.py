"""Analyze: each condition true and false, the universe window, and the corporate-action rule."""

from __future__ import annotations

import datetime as dt

import trader.analyze as analyze
from trader.analyze.conditions import close_above_range_high, quiet_range, volume_multiple
from trader.schema import Action, Bar
from trader.store import Store, month_file

from ..market import history_of, make_market, trading_days


def bars(highs_lows, last_close=100, last_volume=1000):
    days = trading_days(len(highs_lows) + 1)
    out = [Bar(d, "X", 100, h, l, 100, 100, 1000, 0, 1) for d, (h, l) in zip(days, highs_lows)]
    return out + [Bar(days[-1], "X", 100, max(last_close, 100), 99, last_close, 100, last_volume, 0, 1)]


def test_quiet_range():
    assert quiet_range(bars([(104, 97)] * 10), days=10, max_pct=8)[0]          # 7.2% range
    assert not quiet_range(bars([(106, 97)] * 10), days=10, max_pct=8)[0]      # 9.3%


def test_close_above_range_high():
    assert close_above_range_high(bars([(104, 97)] * 10, last_close=105), days=10)[0]
    assert not close_above_range_high(bars([(104, 97)] * 10, last_close=104), days=10)[0]


def test_volume_multiple():
    assert volume_multiple(bars([(104, 97)] * 20, last_volume=2000), min=2, avg_days=20)[0]
    assert not volume_multiple(bars([(104, 97)] * 20, last_volume=1999), min=2, avg_days=20)[0]


def test_universe_uses_only_the_previous_60_days(tmp_path, monkeypatch):
    monkeypatch.setattr(analyze, "UNIVERSE_SIZE", 1)
    days = 70
    h = history_of({"STEADY": [(100, 101, 99, 100)] * days, "SPIKE": [(10, 11, 9, 10)] * days})
    # SPIKE trades a fortune only today, which is outside the 60-day window the universe uses.
    today = h.calendar[-1]
    spike = h._bars["SPIKE"]
    spike[-1] = Bar(today, "SPIKE", 10, 11, 9, 10, 10, 1e12, 1e13, 10)
    store = Store(tmp_path)
    universe = analyze._universe(store, h.as_of(today), store.writer("analyze"), month_file(today, "jsonl"))
    assert universe == ["STEADY"]


def test_a_split_due_inside_the_holding_period_excludes_the_share(tmp_path):
    days = make_market(tmp_path, n_symbols=3, n_days=80)
    today = days[-1]
    soon = Action("S01", today + dt.timedelta(days=3), "split", 2.0, "announced", today - dt.timedelta(days=5), "test")
    store = Store(tmp_path)
    history = store.history()
    history._actions["S01"].append(soon)
    analyze.analyze_day(store, history.as_of(today))
    checks = {r["symbol"]: r for r in store.records_all("analysis") if r["type"] == "check"}
    assert checks["S01"]["results"]["quiet-breakout-v1"]["failed"] == "corporate_action_within_holding_period"
    assert checks["S02"]["results"]["quiet-breakout-v1"]["failed"] != "corporate_action_within_holding_period"
