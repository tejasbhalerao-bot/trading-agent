"""Never look at the future: the spec's most important rule.

Two markets are identical up to a cut-off date and different after it. Every check,
proposal, skip and decision made up to the cut-off must be identical in both.
"""

from __future__ import annotations

import pytest

from trader.run import replay
from trader.store import Store
from trader.store.history import History

from ..market import make_market

DECISION_TYPES = ("proposal", "skip", "decision")


def records(store, folder, types, until):
    return [r for r in store.records_all(folder) if r["type"] in types and r["date"] <= until]


@pytest.fixture
def two_markets(tmp_path):
    days = make_market(tmp_path / "same", n_days=150)
    cut = days[110]
    make_market(tmp_path / "changed", n_days=150, change_after=cut)
    runs = {}
    for name in ("same", "changed"):
        store = Store(tmp_path / f"{name}-run", history_from=tmp_path / name)
        replay(store, days[65], days[-1], quiet=True)
        runs[name] = store
    return runs, cut


def test_the_markets_really_differ_after_the_cut(two_markets):
    runs, cut = two_markets
    a = runs["same"].history().as_of(cut).bars("S00")
    b = runs["changed"].history().as_of(cut).bars("S00")
    assert a == b
    assert runs["same"].history().bars_after_for_test("S00", cut) != runs["changed"].history().bars_after_for_test("S00", cut)


def test_decisions_up_to_the_cut_do_not_depend_on_later_prices(two_markets):
    runs, cut = two_markets
    until = cut.isoformat()
    a = records(runs["same"], "notebook", DECISION_TYPES, until)
    b = records(runs["changed"], "notebook", DECISION_TYPES, until)
    assert a, "the test market should produce decisions before the cut"
    assert any(r["type"] == "decision" and r["action"] == "buy" for r in a)
    assert a == b


def test_checks_up_to_the_cut_do_not_depend_on_later_prices(two_markets):
    runs, cut = two_markets
    until = cut.isoformat()
    types = ("check", "mood", "universe")
    assert records(runs["same"], "analysis", types, until) == records(runs["changed"], "analysis", types, until)


def test_a_view_refuses_to_read_a_later_day(tmp_path):
    days = make_market(tmp_path, n_symbols=2, n_days=10)
    view = Store(tmp_path).history().as_of(days[5])
    assert view.raw_bar("S00", days[5]) is not None
    with pytest.raises(LookupError):
        view.raw_bar("S00", days[6])
    assert [b.date for b in view.bars("S00")] == days[:6]
    assert view.calendar == days[:6]


def test_replaying_twice_gives_identical_notebooks(tmp_path):
    days = make_market(tmp_path / "m", n_days=100)
    out = []
    for name in ("a", "b"):
        store = Store(tmp_path / name, history_from=tmp_path / "m")
        replay(store, days[65], days[-1], quiet=True)
        out.append(b"".join(p.read_bytes() for p in sorted((tmp_path / name / "data" / "notebook").glob("*.jsonl"))))
    assert out[0] == out[1]


# A test-only helper: History has no public way to read past its own data, by design.
def _bars_after(self, symbol, date):
    return [b for b in self._bars.get(symbol, []) if b.date > date]


History.bars_after_for_test = _bars_after
