"""Learn: the four rules from the spec, the switch-off rule, and the confidence check."""

from __future__ import annotations

import datetime as dt

from trader import learn
from trader.store import Store, month_file

D = dt.date(2026, 3, 2)


def setup(tmp_path, trades, shadows=()):
    """trades: (checklist, mood, r) for exits, or (checklist, mood, (worse, better)) for unknowns."""
    store = Store(tmp_path)
    nb, books = [], []
    for i, (cid, mood, r) in enumerate(trades):
        tid = f"2026-02-01/S{i}/{cid}"
        nb.append({"type": "decision", "action": "buy", "id": tid, "checklist": cid, "mood": mood, "stop": 95,
                   "confidence": 0.9, "date": "2026-02-01"})
        res = {"type": "result", "id": tid, "date": "2026-02-05", "symbol": f"S{i}", "entry_price": 100}
        if isinstance(r, tuple):
            res.update(outcome="unknown", r_multiple_worse=r[0], r_multiple_better=r[1])
        else:
            res.update(outcome="exited", r_multiple=r)
        nb.append(res)
    store.writer("record").append_records(month_file(D, "jsonl"), nb)
    if shadows:
        store.writer("settle").append_records(month_file(D, "jsonl"), list(shadows))
    return store


def test_unknowns_are_kept_as_a_range_never_dropped(tmp_path):
    store = setup(tmp_path, [("c", "up", 1.5), ("c", "up", (-1, 1.5))])
    v = learn.learn_day(store, D)
    cell = v["cells"]["c|up"]
    assert cell["paper_trades"] == 2 and cell["unknown"] == 1
    assert cell["win_rate_range"] == [0.5, 1.0]
    assert cell["avg_r_range"] == [0.25, 1.5]


def test_confidence_uses_the_cautious_end_and_borrows_when_evidence_is_thin(tmp_path):
    store = setup(tmp_path, [("c", "up", 1.5), ("c", "up", (-1, 1.5))])
    cell = learn.learn_day(store, D)["cells"]["c|up"]
    assert 0.0 < cell["confidence"] < 0.75   # one cautious win out of two, pulled towards the overall record


def test_skipped_candidates_never_move_trust_scores(tmp_path):
    shadows = [{"type": "event", "event": "shadow_exited", "checklist": "c", "r_multiple": 1.5, "date": "2026-02-05",
                "id": f"x{i}", "symbol": "X"} for i in range(12)]
    plain = learn.learn_day(setup(tmp_path / "a", [("c", "up", -1.0)] * 3), D)
    with_shadows = learn.learn_day(setup(tmp_path / "b", [("c", "up", -1.0)] * 3, shadows), D)
    assert plain["cells"] == with_shadows["cells"]
    assert with_shadows["suggestions"] and not plain["suggestions"]


def test_a_cell_switches_off_only_when_even_its_best_case_loses(tmp_path):
    losing = learn.learn_day(setup(tmp_path / "a", [("c", "down", -1.0)] * 9 + [("c", "down", -0.9)] * 3), D)
    assert losing["cells"]["c|down"]["switched_off"]
    hopeful = learn.learn_day(setup(tmp_path / "b", [("c", "down", -1.0)] * 11 + [("c", "down", (-1, 1.5))] * 6), D)
    assert not hopeful["cells"]["c|down"]["switched_off"]
    few = learn.learn_day(setup(tmp_path / "c", [("c", "down", -1.0)] * 9), D)
    assert not few["cells"]["c|down"]["switched_off"]


def test_the_confidence_check_calls_out_overconfidence(tmp_path):
    v = learn.learn_day(setup(tmp_path, [("c", "up", -1.0)] * 20 + [("c", "up", 1.5)] * 2), D)
    assert v["calibration_overall"]["verdict"] == "overconfident"   # said 90%, won 2 of 22


def test_a_new_version_only_when_new_results_arrive_and_it_lists_its_evidence(tmp_path):
    store = setup(tmp_path, [("c", "up", 1.5)])
    v1 = learn.learn_day(store, D)
    assert learn.learn_day(store, D + dt.timedelta(days=1)) is None
    assert v1["cells"]["c|up"]["evidence"] == ["2026-02-01/S0/c"]
    assert v1["changes"] == []
