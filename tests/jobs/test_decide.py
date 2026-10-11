"""Decide: the losing-run brake, worked out from the account's history."""

from __future__ import annotations

from trader.decide import brake_state

LIMITS = {"losing_run_brake": {"halve_risk_below_peak_pct": 10, "pause_new_buys_below_peak_pct": 15, "pause_trading_days": 10}}


def snaps(balances):
    out, peak = [], 0
    for b in balances:
        peak = max(peak, b)
        out.append({"balance_worse": b, "peak": peak})
    return out


def test_normal_while_within_ten_percent():
    assert brake_state(snaps([10000, 9500, 9100]), LIMITS)["mode"] == "normal"


def test_half_risk_from_ten_percent_below_the_peak():
    assert brake_state(snaps([10000, 8900]), LIMITS)["mode"] == "half"


def test_paused_for_ten_trading_days_from_fifteen_percent_below():
    s = snaps([10000, 8400] + [8400] * 9)
    assert brake_state(s, LIMITS)["mode"] == "paused"
    assert brake_state(snaps([10000, 8400] + [8400] * 10), LIMITS)["mode"] == "half after pause"


def test_no_new_pause_until_the_account_recovers():
    after = snaps([10000, 8400] + [8400] * 10 + [8000])
    assert brake_state(after, LIMITS)["mode"] == "half after pause"
    recovered = snaps([10000, 8400] + [8400] * 10 + [9200])
    assert brake_state(recovered, LIMITS)["mode"] == "normal"
