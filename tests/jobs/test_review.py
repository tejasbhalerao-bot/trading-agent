"""The check on Claude's review: one test per rejection rule in the design."""

from __future__ import annotations

import json

from trader.schema.review import check_review

DATE = "2026-10-12"
IDS = {"2026-10-12/AAA/quiet-breakout-v1", "2026-10-12/BBB/gap-up-holds-v1"}
A = "2026-10-12/AAA/quiet-breakout-v1"


def review(*items, date=DATE):
    return json.dumps({"date": date, "reviews": list(items)})


def test_a_good_review_with_a_veto_passes():
    ok, problems = check_review(review({"id": A, "case": "Tight range, then a clean break on heavy volume.",
                                        "veto": {"category": "event", "reason": "Quarterly results are due on 13 October."}}),
                                DATE, IDS)
    assert ok and not problems


def test_missing_review_is_reported_not_crashed():
    assert check_review(None, DATE, IDS) == (None, ["no review arrived"])


def test_wrong_date_is_rejected():
    assert check_review(review({"id": A, "case": "x"}, date="2026-10-11"), DATE, IDS)[0] is None


def test_a_trade_that_was_not_proposed_is_rejected():
    _, problems = check_review(review({"id": "2026-10-12/ZZZ/quiet-breakout-v1", "case": "x"}), DATE, IDS)
    assert "was not proposed" in problems[0]


def test_the_same_trade_twice_is_rejected():
    _, problems = check_review(review({"id": A, "case": "x"}, {"id": A, "case": "y"}), DATE, IDS)
    assert any("twice" in p for p in problems)


def test_a_veto_outside_the_list_or_without_a_real_reason_is_rejected():
    _, p1 = check_review(review({"id": A, "case": "x", "veto": {"category": "gut_feeling", "reason": "I just do not like it at all"}}), DATE, IDS)
    _, p2 = check_review(review({"id": A, "case": "x", "veto": {"category": "event", "reason": "results"}}), DATE, IDS)
    assert "not on the list" in p1[0] and "at least" in p2[0]


def test_anything_extra_is_rejected():
    _, p1 = check_review(review({"id": A, "case": "x", "quantity": 100}), DATE, IDS)
    _, p2 = check_review(json.dumps({"date": DATE, "reviews": [], "new_trades": ["CCC"]}), DATE, IDS)
    assert p1 and p2


def test_an_overlong_case_is_rejected():
    _, problems = check_review(review({"id": A, "case": "word " * 121}), DATE, IDS)
    assert "over 120 words" in problems[0]
