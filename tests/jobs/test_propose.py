"""The evening run's first part: catching up missed evenings, waiting for NSE, and closed days.

NSE is replaced by a stand-in: the synthetic history already holds every price, so Fetch
only needs to report whether today's file is out.
"""

from __future__ import annotations

import datetime as dt

import pytest

from trader import fetch
from trader.fetch import Delivery
from trader.run import IST, propose, replay
from trader.store import Store

from ..market import make_market


@pytest.fixture
def nse(monkeypatch):
    state = {"today_published": True}
    monkeypatch.setattr(fetch, "fetch_reference", lambda store, d: {"holidays": None, "symbol_changes": None})
    monkeypatch.setattr(fetch, "fetch_corporate_actions", lambda *a, **k: None)
    monkeypatch.setattr(fetch, "fetch_day", lambda store, d, historical=True:
                        Delivery(d, "failed" if not state["today_published"] else "market_closed"))
    return state


def runs(store, d):
    return [r["stage"] for r in store.records_all("notebook") if r["type"] == "run" and r["date"] == d.isoformat()]


def at(d, hour):
    return dt.datetime.combine(d, dt.time(hour, 0), IST)


def test_missed_evenings_are_caught_up_without_decisions(tmp_path, nse):
    days = make_market(tmp_path, n_days=110)
    store = Store(tmp_path)
    replay(store, days[70], days[-4], quiet=True)          # the last two evenings before today were missed
    propose(store, days[-1], at(days[-1], 19), do_publish=False)
    assert "caught up" in runs(store, days[-3]) and "caught up" in runs(store, days[-2])
    assert "proposed" in runs(store, days[-1])
    assert not [r for r in store.records_all("notebook") if r["type"] == "proposal" and r["date"] == days[-2].isoformat()]


def test_running_twice_does_nothing_the_second_time(tmp_path, nse):
    days = make_market(tmp_path, n_days=110)
    store = Store(tmp_path)
    replay(store, days[70], days[-2], quiet=True)
    propose(store, days[-1], at(days[-1], 19), do_publish=False)
    assert propose(store, days[-1], at(days[-1], 20), do_publish=False) == "already proposed today"


def test_before_9pm_a_missing_file_means_try_again_later_and_nothing_is_written(tmp_path, nse):
    days = make_market(tmp_path, n_days=110)
    store = Store(tmp_path)
    replay(store, days[70], days[-1], quiet=True)
    tomorrow = days[-1] + dt.timedelta(days=3 if days[-1].weekday() == 4 else 1)
    nse["today_published"] = False
    before = len(store.records_all("notebook"))
    assert "retry" in propose(store, tomorrow, at(tomorrow, 18), do_publish=False)
    assert len(store.records_all("notebook")) == before


def test_on_a_weekend_with_no_file_the_market_is_closed_but_missed_days_are_still_caught_up(tmp_path, nse):
    days = make_market(tmp_path, n_days=110)
    store = Store(tmp_path)
    replay(store, days[70], days[-3], quiet=True)
    saturday = days[-1] + dt.timedelta(days=(5 - days[-1].weekday()) % 7 or 7)
    nse["today_published"] = False
    assert propose(store, saturday, at(saturday, 22), do_publish=False).startswith("market closed")
    assert "caught up" in runs(store, days[-2]) and "caught up" in runs(store, days[-1])
    assert runs(store, saturday) == ["closed"]
