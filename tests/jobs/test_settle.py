"""Settle, one test per row of the entry and exit tables in docs/design/pass2-settle.md.

A buy is decided on day 0 (close 100) with stop 95, target 110, 10 shares, time limit 3 days.
Each tuple below is one trading day's (open, high, low, close).
"""

from __future__ import annotations

from trader.schema import Action
from trader.settle import settle_day
from trader.store import Store, month_file

from ..market import history_of

DAY0 = (100, 101, 99, 100)
QUIET = (100, 102, 98, 101)


def run(tmp_path, days, others=None, actions=(), name="t"):
    bars = {"X": [DAY0] + days}
    if others:
        bars["Y"] = [DAY0] * others
    h = history_of(bars, actions)
    store = Store(tmp_path / name)
    d0 = h.calendar[0]
    store.writer("record").append_records(month_file(d0, "jsonl"), [{
        "type": "decision", "action": "buy", "id": "t", "symbol": "X", "date": d0.isoformat(),
        "quantity": 10, "stop": 95, "target": 110, "max_hold_days": 3}])
    for d in h.calendar[1:]:
        settle_day(store, h.as_of(d), 10_000)
    books = store.records_all("books")
    return [r for r in books if r["type"] == "event"], [r for r in books if r["type"] == "snapshot"], h


def only(events, kind):
    found = [e for e in events if e["event"] == kind]
    assert len(found) == 1, events
    return found[0]


# Entering

def test_enters_at_the_open_when_it_opens_between_stop_and_target(tmp_path):
    events, _, _ = run(tmp_path, [QUIET])
    assert only(events, "entered")["price"] == 100


def test_not_entered_when_it_opens_at_or_below_the_stop(tmp_path):
    events, _, _ = run(tmp_path, [(94, 96, 93, 95)])
    assert only(events, "not_entered")["reason"] == "opened beyond its exit"


def test_not_entered_when_it_opens_at_or_above_the_target(tmp_path):
    events, _, _ = run(tmp_path, [(111, 112, 110, 111)])
    assert only(events, "not_entered")["reason"] == "opened beyond its exit"


def test_not_entered_on_a_locked_day(tmp_path):
    events, _, _ = run(tmp_path, [(100, 100, 100, 100)])
    assert only(events, "not_entered")["reason"] == "could not trade"


def test_waits_for_a_missing_price_then_gives_up_after_five_days(tmp_path):
    events, _, _ = run(tmp_path, [], others=7)
    assert [e["event"] for e in events] == ["waiting"] * 4 + ["not_entered"]
    assert events[-1]["reason"] == "no price for 5 trading days"


# Exiting

def test_gap_through_the_stop_is_booked_at_the_open_not_the_stop(tmp_path):
    events, _, _ = run(tmp_path, [QUIET, (93, 94, 92, 93)])
    e = only(events, "exited")
    assert (e["price"], e["reason"]) == (93, "gapped through the stop")


def test_gap_through_the_target_is_booked_at_the_open(tmp_path):
    events, _, _ = run(tmp_path, [QUIET, (112, 113, 111, 112)])
    e = only(events, "exited")
    assert (e["price"], e["reason"]) == (112, "gapped through the target")


def test_a_day_touching_both_stop_and_target_is_unknown_and_valued_both_ways(tmp_path):
    events, snaps, _ = run(tmp_path, [(100, 111, 94, 100)])
    e = only(events, "unknown")
    assert (e["worse"], e["better"]) == (95, 110)
    assert snaps[-1]["gap"] == 10 * (110 - 95)
    assert snaps[-1]["balance_worse"] == 10_000 - 10 * 100 + 10 * 95


def test_exits_at_the_stop_when_the_low_touches_it(tmp_path):
    events, _, _ = run(tmp_path, [(100, 101, 94.5, 96)])
    assert only(events, "exited")["price"] == 95


def test_exits_at_the_target_when_the_high_touches_it(tmp_path):
    events, _, _ = run(tmp_path, [(100, 111, 99, 105)])
    assert only(events, "exited")["price"] == 110


def test_time_limit_sells_at_the_open_after_three_counted_days(tmp_path):
    events, _, h = run(tmp_path, [QUIET, QUIET, QUIET, (102, 103, 101, 102)])
    e = only(events, "exited")
    assert (e["price"], e["reason"], e["date"]) == (102, "time limit", h.calendar[4].isoformat())


def test_a_locked_day_does_not_count_towards_the_time_limit(tmp_path):
    events, _, h = run(tmp_path, [QUIET, (101, 101, 101, 101), QUIET, QUIET, (102, 103, 101, 102)])
    assert only(events, "exited")["date"] == h.calendar[5].isoformat()


def test_a_split_during_a_trade_leaves_value_and_risk_unchanged(tmp_path):
    from ..market import trading_days
    split_day = trading_days(3)[2]
    split = Action("X", split_day, "split", 2.0, "verified", split_day, "test")
    events, snaps, _ = run(tmp_path, [QUIET, (50, 51, 49, 50)], actions=[split])
    only(events, "adjusted")
    p = snaps[-1]["positions"][0]
    assert (p["qty"], p["entry"], p["stop"], p["target"]) == (20, 50, 47.5, 55)
    assert p["qty"] * p["entry"] == 10 * 100 and p["qty"] * (p["entry"] - p["stop"]) == 10 * (100 - 95)


def test_settling_the_same_days_twice_gives_identical_books(tmp_path):
    days = [QUIET, (100, 111, 99, 105), QUIET]
    a = run(tmp_path, days, name="a")
    b = run(tmp_path, days, name="b")
    assert a[0] == b[0] and a[1] == b[1]


def test_a_trade_open_across_a_broken_price_history_is_unknown_not_a_fake_loss(tmp_path):
    from ..market import trading_days
    broke = trading_days(3)[2]
    restart = Action("X", broke, "restart", 1.0, "verified", broke, "test")
    events, _, _ = run(tmp_path, [QUIET, (10, 10.2, 9.8, 10)], actions=[restart])
    e = only(events, "unknown")
    assert "broke" in e["reason"] and (e["worse"], e["better"]) == (95, 110)
