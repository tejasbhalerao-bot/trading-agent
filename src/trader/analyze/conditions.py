"""The named conditions checklists are built from. Each answers yes or no from the numbers,
and returns the figures it used, so the record shows exactly what was seen."""

from __future__ import annotations

from trader.schema import Bar


def quiet_range(bars: list[Bar], days: int, max_pct: float) -> tuple[bool, dict]:
    window = bars[-days - 1:-1]
    hi, lo = max(b.high for b in window), min(b.low for b in window)
    pct = (hi - lo) / lo * 100
    return pct <= max_pct, {f"range_{days}d_pct": round(pct, 2)}


def close_above_range_high(bars: list[Bar], days: int) -> tuple[bool, dict]:
    hi = max(b.high for b in bars[-days - 1:-1])
    return bars[-1].close > hi, {f"high_{days}d": hi}


def volume_multiple(bars: list[Bar], min: float, avg_days: int) -> tuple[bool, dict]:  # noqa: A002 - matches the YAML key
    avg = sum(b.volume for b in bars[-avg_days - 1:-1]) / avg_days
    multiple = bars[-1].volume / avg if avg else 0.0
    return multiple >= min, {"volume_multiple": round(multiple, 2), f"avg_volume_{avg_days}d": round(avg)}


def above_rising_average(bars: list[Bar], days: int, lookback: int) -> tuple[bool, dict]:
    closes = [b.close for b in bars]
    now = sum(closes[-days:]) / days
    then = sum(closes[-days - lookback:-lookback]) / days
    return closes[-1] > now and now > then, {f"avg_{days}d": round(now, 2), f"avg_{days}d_{lookback}_days_ago": round(then, 2)}


def lower_closes(bars: list[Bar], days: int) -> tuple[bool, dict]:
    closes = [b.close for b in bars[-days - 1:]]
    falls = sum(1 for a, b in zip(closes, closes[1:]) if b < a)
    return falls == days, {f"lower_closes_of_last_{days}": falls}


def gap_up(bars: list[Bar], min_pct: float) -> tuple[bool, dict]:
    pct = (bars[-1].open / bars[-2].close - 1) * 100
    return pct >= min_pct, {"gap_pct": round(pct, 2)}


def holds_gain(bars: list[Bar], top_fraction: float) -> tuple[bool, dict]:
    b = bars[-1]
    position = (b.close - b.low) / (b.high - b.low) if b.high > b.low else 0.0
    return b.close >= b.open and position >= 1 - top_fraction, {"close_position_in_range": round(position, 3)}


CONDITIONS = {
    "quiet_range": quiet_range,
    "close_above_range_high": close_above_range_high,
    "volume_multiple": volume_multiple,
    "above_rising_average": above_rising_average,
    "lower_closes": lower_closes,
    "gap_up": gap_up,
    "holds_gain": holds_gain,
}


def typical_daily_move(bars: list[Bar], days: int = 14) -> float:
    """Average true range: the average daily swing, including overnight gaps."""
    recent = bars[-days - 1:]
    ranges = [max(b.high, p.close) - min(b.low, p.close) for p, b in zip(recent, recent[1:])]
    return sum(ranges) / len(ranges)
