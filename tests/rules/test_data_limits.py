"""GitHub warns at 50 MB per file and blocks at 100 MB (docs/design/constraints.md).
Every data file must stay under half the warning, and every growing store holds one month per file."""

from __future__ import annotations

import re
from pathlib import Path

DATA = Path(__file__).resolve().parents[2] / "data"
LIMIT_BYTES = 25 * 1024 * 1024
MONTHLY = re.compile(r"^\d{4}-\d{2}\.(csv|jsonl)$")
DAILY_REPORT = re.compile(r"^\d{4}-\d{2}-\d{2}\.md$")
SINGLE_FILES = {"identity.csv", "holidays.csv", "RECORD_START"}


def data_files():
    return [p for p in DATA.rglob("*") if p.is_file()] if DATA.exists() else []


def test_no_data_file_is_near_githubs_limit():
    big = [f"{p.relative_to(DATA)}: {p.stat().st_size / 1e6:.0f} MB" for p in data_files() if p.stat().st_size > LIMIT_BYTES]
    assert not big, big


def test_growing_stores_use_one_file_per_month():
    odd = [str(p.relative_to(DATA)) for p in data_files()
           if p.name not in SINGLE_FILES and "_probe" not in p.parts and not MONTHLY.match(p.name)
           and not (p.parts[-3:-2] == ("reports",) and DAILY_REPORT.match(p.name))]
    assert not odd, odd
